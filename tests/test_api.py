"""Contract, storage and actual checkpoint tests. Generated inputs are test fixtures only."""
import copy
import json
import os
import threading
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient
from backend import submission_api as api

class SubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory=Path(os.environ.get('MOTIONAI_TEST_DATA',str(api.ROOT/'tests'/'.test-data')))
        directory.mkdir(parents=True,exist_ok=True)
        api.DB_PATH=directory/(str(uuid.uuid4())+'.sqlite')
        api.load_model()
        cls.client=TestClient(api.app)
        cls.fixture=cls.recording()

    @staticmethod
    def recording():
        frames=[]
        for i in range(20):
            joints=[{'x':.5,'y':.5,'z':0.,'visibility':.95} for _ in range(33)]
            positions={0:(.5,.12),7:(.47,.12),8:(.53,.12),11:(.4,.25),12:(.6,.25),13:(.36,.4),14:(.64,.4),15:(.32,.55),16:(.68,.55),23:(.43,.5),24:(.57,.5),25:(.42-i*.001,.7),26:(.58+i*.001,.7),27:(.4,.9),28:(.6,.9)}
            for key,(x,y) in positions.items():joints[key].update(x=x,y=y)
            frames.append({'timestamp':50+i*50,'image':copy.deepcopy(joints),'world':copy.deepcopy(joints),'width':1280,'height':720,'metrics':{'left':170.,'right':169.,'primary':169.5,'feedback':'Test fixture: starting pose','rest':True,'peak':False,'visible':8,'bodyAngle':170}})
        return {'exercise':'squat','date':'2026-09-16T12:00:00Z','reps':0,'duration':1,'target':10,'source':'import','frames':frames}

    def test_checkpoint_loaded_strictly(self):
        result=self.client.get('/api/health').json()
        self.assertTrue(result['motionbert']['loaded'],result['motionbert']['error'])
        self.assertEqual(result['motionbert']['parameters'],16001549)
        self.assertEqual(result['motionbert']['checkpoint_sha256'],'9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f')

    def test_h36m_adapter_channels_and_aspect_ratio(self):
        result=api.mediapipe_to_h36m(self.fixture['frames'])
        self.assertEqual(result.shape,(20,17,3))
        self.assertAlmostEqual(float(result[0,11,0]),(.4*1280-640)/360,places=5)
        self.assertAlmostEqual(float(result[0,11,2]),.95,places=5)
        self.assertAlmostEqual(float(result[0,0,0]),0.,places=5)
        self.assertLess(result[0,10,2],result[0,9,2])

    def test_storage_inference_cache_and_deletion(self):
        created=self.client.post('/api/sessions',json=self.fixture)
        self.assertEqual(created.status_code,201,created.text)
        session=created.json();session_id=session['id']
        self.assertIsNone(session['motionbert'])
        self.assertEqual(self.client.get('/api/sessions/'+session_id).json()['frames'],self.fixture['frames'])
        response=self.client.post('/api/sessions/'+session_id+'/analyze')
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()['motionbert']
        self.assertEqual(np.array(result['frames']).shape,(20,17,3))
        self.assertTrue(np.isfinite(result['frames']).all())
        self.assertGreater(result['latency_ms'],0)
        self.assertEqual(result['windows'],1)
        self.assertEqual(len(result['trajectories']['left']),20)
        self.assertEqual(self.client.post('/api/sessions/'+session_id+'/analyze').json()['motionbert'],result)
        self.assertTrue(next(s for s in self.client.get('/api/sessions').json() if s['id']==session_id)['analyzed'])
        self.assertEqual(self.client.delete('/api/sessions/'+session_id).status_code,200)
        self.assertEqual(self.client.get('/api/sessions/'+session_id).status_code,404)

    def test_reject_invalid_recordings(self):
        examples=[]
        value=copy.deepcopy(self.fixture);value['frames'][1]['timestamp']=value['frames'][0]['timestamp'];examples.append(value)
        value=copy.deepcopy(self.fixture);value['frames'][0]['image']=[];examples.append(value)
        value=copy.deepcopy(self.fixture);value['exercise']='unknown';examples.append(value)
        value=copy.deepcopy(self.fixture);value['frames'][0]['width']=0;examples.append(value)
        value=copy.deepcopy(self.fixture);value['frames'][0]['metrics']['left']=200;examples.append(value)
        value=copy.deepcopy(self.fixture);value['date']={};examples.append(value)
        value=copy.deepcopy(self.fixture);value['frames'][0]['width']=True;examples.append(value)
        value=copy.deepcopy(self.fixture);value['frames'][0]['metrics']['left']=None;value['frames'][0]['metrics']['right']=None;examples.append(value)
        value=copy.deepcopy(self.fixture);value['frames'][0]['metrics']['leftReliable']=False;examples.append(value)
        for example in examples:self.assertEqual(self.client.post('/api/sessions',json=example).status_code,422)

    def test_unavailable_side_is_stored_as_null(self):
        value=copy.deepcopy(self.fixture)
        for frame in value['frames']:
            frame['metrics'].update(left=None,leftReliable=False,rightReliable=True,bodyAngle=None,primary=169.)
        response=self.client.post('/api/sessions',json=value)
        self.assertEqual(response.status_code,201,response.text)
        session=response.json()
        self.assertIsNone(session['frames'][0]['metrics']['left'])
        self.assertEqual(session['frames'][0]['metrics']['primary'],169.)
        result=self.client.post('/api/sessions/'+session['id']+'/analyze')
        self.assertEqual(result.status_code,200,result.text)
        self.client.delete('/api/sessions/'+session['id'])

    def test_nonfinite_extra_metrics_do_not_crash_storage(self):
        value=copy.deepcopy(self.fixture)
        value['frames'][0]['metrics']['bodyAngle']=float('nan')
        response=self.client.post('/api/sessions',content=json.dumps(value),headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,422,response.text)

    def test_recovery_retry_does_not_duplicate_or_overwrite(self):
        value=copy.deepcopy(self.fixture);value['client_id']=str(uuid.uuid4())
        first=self.client.post('/api/sessions',json=value)
        self.assertEqual(first.status_code,201,first.text)
        retry=self.client.post('/api/sessions',json=value)
        self.assertEqual(retry.json(),first.json())
        self.assertEqual(sum(s['id']==value['client_id'] for s in self.client.get('/api/sessions').json()),1)
        changed=copy.deepcopy(value);changed['reps']=2
        self.assertEqual(self.client.post('/api/sessions',json=changed).status_code,409)
        self.assertEqual(self.client.get('/api/sessions/'+value['client_id']).json()['reps'],0)
        self.client.delete('/api/sessions/'+value['client_id'])

    def test_camera_assets_and_missing_asset_status(self):
        self.assertTrue(self.client.get('/api/health').json()['camera']['ready'])
        response=self.client.get('/mediapipe/wasm/vision_wasm_internal.wasm')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['content-type'],'application/wasm')
        self.assertEqual(response.content[:4],b'\x00asm')
        for path in ('/mediapipe/missing.task','/assets/missing.js','/missing.wasm','/api/unknown'):
            response=self.client.get(path)
            self.assertEqual(response.status_code,404,path)
            self.assertNotIn('text/html',response.headers['content-type'])
        self.assertEqual(self.client.get('/studio').status_code,200)

    def test_camera_app_starts_while_motionbert_loads(self):
        started=threading.Event();release=threading.Event();finished=threading.Event()
        def slow_model():
            started.set();release.wait(5);finished.set()
        try:
            with patch.object(api,'load_model',slow_model),TestClient(api.app) as client:
                self.assertTrue(started.wait(1))
                self.assertFalse(finished.is_set(),'Startup waited for MotionBERT instead of serving the app.')
                self.assertEqual(client.get('/').status_code,200)
                self.assertTrue(client.get('/api/health').json()['camera']['ready'])
        finally:
            release.set();finished.wait(1)

    def test_profile_and_origin_protection(self):
        profile={'name':'Test athlete','weeklyGoal':4,'repTarget':12,'audio':False}
        self.assertEqual(self.client.put('/api/profile',json=profile).json(),profile)
        self.assertEqual(self.client.get('/api/profile').json(),profile)
        self.assertEqual(self.client.put('/api/profile',json={**profile,'weeklyGoal':0}).status_code,422)
        self.assertEqual(self.client.post('/api/sessions',json=self.fixture,headers={'Origin':'https://external.invalid'}).status_code,403)
        self.assertEqual(self.client.post('/api/sessions',json=self.fixture,headers={'Content-Length':'invalid'}).status_code,400)
        self.assertEqual(self.client.post('/api/sessions',json=self.fixture,headers={'Content-Length':'30000001'}).status_code,413)

if __name__=='__main__':unittest.main(verbosity=2)
