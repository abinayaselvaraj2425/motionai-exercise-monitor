import copy
import tempfile
import unittest
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from backend import submission_api as api
from tests.test_api import SubmissionTests

class RoutineTests(unittest.TestCase):
    def setUp(self):
        self.previous=api.DB_PATH;self.path=api.ROOT/'tests'/'.test-data'/('routine-'+str(uuid.uuid4())+'.sqlite');self.path.parent.mkdir(exist_ok=True);api.DB_PATH=self.path;self.client=TestClient(api.app)
    def tearDown(self):
        self.client.close();api.DB_PATH=self.previous;self.path.unlink(missing_ok=True)
    def start(self):
        r=self.client.post('/api/routines',json={'id':str(uuid.uuid4()),'template':'standing'});self.assertEqual(r.status_code,201,r.text);return r.json()
    def patch(self,r,body):return self.client.patch('/api/routines/'+r['id'],json=body)
    def test_cross_origin_routine_changes_are_rejected(self):
        r=self.start();response=self.client.patch('/api/routines/'+r['id'],json={'finish':True},headers={'origin':'https://another-site.example'});self.assertEqual(response.status_code,403)
    def test_start_is_persistent_and_retry_safe(self):
        r=self.start();again=self.client.post('/api/routines',json={'id':r['id'],'template':'standing'});self.assertEqual(again.json()['steps'],r['steps']);self.assertEqual(len(self.client.get('/api/routines').json()),1)
    def test_invalid_and_out_of_order_steps_rejected(self):
        r=self.start();self.assertEqual(self.patch(r,{'step':2,'status':'skipped'}).status_code,409);self.assertEqual(self.patch(r,{'step':True,'status':'done'}).status_code,422);self.patch(r,{'step':0,'status':'done'});self.assertEqual(self.patch(r,{'step':1,'status':'done'}).status_code,422)
    def test_saved_recording_reconciles_after_reload_and_completion(self):
        r=self.start();self.patch(r,{'step':0,'status':'done'})
        for step in r['steps'][1:3]:
            recording=copy.deepcopy(SubmissionTests.recording());recording.update(client_id=step['recording_id'],exercise=step['exercise'],source='camera',reps=step['target'],target=step['target']);response=self.client.post('/api/sessions',json=recording);self.assertEqual(response.status_code,201,response.text)
        run=self.client.get('/api/routines').json()[0];self.assertEqual(run['reps'],16);self.assertEqual(run['steps'][2]['status'],'done');self.patch(r,{'step':3,'status':'done'});done=self.patch(r,{'finish':True}).json();self.assertTrue(done['complete']);self.assertEqual(done['duration'],77);self.assertIsNotNone(done['ended']);self.assertEqual(self.patch(r,{'finish':True}).json()['ended'],done['ended'])
    def test_early_finish_never_reports_completed(self):
        r=self.start();done=self.patch(r,{'finish':True}).json();self.assertFalse(done['complete']);self.assertTrue(all(s['status']=='skipped' for s in done['steps']))
    def test_below_target_and_deleted_recordings_are_honest(self):
        r=self.start();self.patch(r,{'step':0,'status':'skipped'});step=r['steps'][1];recording=SubmissionTests.recording();recording.update(client_id=step['recording_id'],exercise=step['exercise'],source='camera',reps=2,target=8);self.client.post('/api/sessions',json=recording)
        run=self.patch(r,{'finish':True}).json();self.assertEqual(run['steps'][1]['status'],'partial');self.assertFalse(run['complete']);self.client.delete('/api/sessions/'+step['recording_id']);run=self.client.get('/api/routines').json()[0];self.assertEqual(run['steps'][1]['status'],'missing');self.assertEqual(run['reps'],0)

if __name__=='__main__':unittest.main()
