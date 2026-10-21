import copy
import json
import math
import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import submission_api as api
from backend.reports import report
from tests import sign_in
from tests import test_api

def movement(date='2026-10-19T12:00:00Z'):
    s=test_api.SubmissionTests.recording();s.update(date=date,reps=4,duration=10,target=8)
    frames=[]
    for i in range(101):
        t=i/10;deg=170-50*(1-math.cos(2*math.pi*t/2))/2
        f=copy.deepcopy(s['frames'][0]);f['timestamp']=i*100
        for side in (0,1):
            x=.4+.2*side
            for key,point in {23+side:(x,.35,0),25+side:(x,.55,0),27+side:(x+.18*math.sin(math.radians(deg)),.55-.18*math.cos(math.radians(deg)),0)}.items():
                for source in ('image','world'):f[source][key].update(zip(('x','y','z'),point))
        frames.append(f)
    s['frames']=frames
    return s

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(api.app,client=('test-'+uuid.uuid4().hex,50000))
        self.credentials,self.recovery=sign_in(self.client)
    def tearDown(self):self.client.close()

    def test_authentication_and_account_isolation(self):
        s=self.client.post('/api/sessions',json=movement()).json()
        other=TestClient(api.app,client=('other-'+uuid.uuid4().hex,50001))
        self.assertEqual(other.get('/api/sessions').status_code,401)
        sign_in(other)
        self.assertEqual(other.get('/api/sessions').json(),[])
        self.assertEqual(other.get('/api/sessions/'+s['id']).status_code,404)
        self.assertEqual(other.get('/api/sessions/'+s['id']+'/report').status_code,404)
        self.assertEqual(other.post('/api/sessions/'+s['id']+'/analyze').status_code,503 if api.model is None else 404)
        other.close()

    def test_report_uses_coordinates_and_never_trusts_imported_metrics(self):
        s=movement();s['motionbert']=None;r=report(s)
        self.assertGreaterEqual(r['measured_cycles'],4)
        self.assertGreater(r['coverage'],90)
        self.assertGreater(next(m['value'] for m in r['metrics'] if m['key']=='range'),40)
        for f in s['frames']:f['metrics']['primary']=0;f['metrics']['left']=0;f['metrics']['right']=0
        self.assertEqual(report(s)['metrics'],r['metrics'])

    def test_missing_visibility_is_unavailable_not_zero(self):
        s=movement()
        for f in s['frames']:
            for j in f['image']:j['visibility']=0
        r=report(s)
        self.assertEqual(r['coverage'],0)
        self.assertTrue(all(m['value'] is None for m in r['metrics']))

    def test_previous_two_comparisons_and_trend_source(self):
        for day in (17,18,19):
            result=self.client.post('/api/sessions',json=movement(f'2026-10-{day}T12:00:00Z'))
            self.assertEqual(result.status_code,201,result.text)
        sid=result.json()['id'];r=self.client.get('/api/sessions/'+sid+'/report').json()
        self.assertEqual(len(r['comparison']['previous']),2)
        self.assertEqual(r['comparison']['changes'][0]['delta'],0)
        trend=self.client.get('/api/trends?exercise=squat&metric=range&source=camera').json()
        self.assertEqual(len(trend),3)
        self.assertEqual(self.client.get('/api/trends?exercise=squat&source=motionbert').json(),[])

    def test_backup_roundtrip_deduplicates_and_strips_untrusted_model(self):
        original=self.client.post('/api/sessions',json=movement()).json()
        backup=self.client.get('/api/export?format=json').json()
        self.assertEqual(len(backup['sessions']),1)
        preview=self.client.post('/api/import/preview',json=backup)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['duplicates'],1)
        other=TestClient(api.app,client=('import-'+uuid.uuid4().hex,50001));sign_in(other)
        backup['sessions'][0]['motionbert']={'frames':[[999]],'status':'complete'}
        result=other.post('/api/import',json=backup)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['sessions'],1)
        sid=other.get('/api/sessions').json()[0]['id']
        self.assertIsNone(other.get('/api/sessions/'+sid).json()['motionbert'])
        self.assertEqual(other.post('/api/import',json=backup).json()['duplicates'],1)
        other.close()

    def test_routine_backup_keeps_recording_links_and_guided_steps(self):
        r=self.client.post('/api/routines',json={'id':str(uuid.uuid4()),'template':'standing'}).json()
        self.client.patch('/api/routines/'+r['id'],json={'step':0,'status':'done'})
        step=r['steps'][1];s=movement();s.update(exercise=step['exercise'],client_id=step['recording_id'],source='camera')
        self.client.post('/api/sessions',json=s)
        self.client.patch('/api/routines/'+r['id'],json={'finish':True})
        backup=self.client.get('/api/export?format=json&routine_id='+r['id']).json()
        other=TestClient(api.app,client=('routine-'+uuid.uuid4().hex,50001));sign_in(other)
        result=other.post('/api/import',json=backup)
        self.assertEqual(result.status_code,200,result.text)
        imported=other.get('/api/routines').json()[0]
        self.assertEqual(imported['steps'][0]['duration'],30)
        sid=imported['steps'][1]['session_id']
        self.assertEqual(other.get('/api/sessions/'+sid).status_code,200)
        self.assertEqual(other.post('/api/import',json=backup).json()['routines'],0)
        other.close()

    def test_csv_has_measurements_and_day_boundaries(self):
        self.client.post('/api/sessions',json=movement())
        response=self.client.get('/api/export',params={'format':'csv','start':'2026-10-19T00:00:00Z','end':'2026-10-20T00:00:00Z'})
        self.assertIn('range_degrees',response.text)
        self.assertIn('Bodyweight squat',response.text)
        self.assertNotIn('Bodyweight squat',self.client.get('/api/export',params={'format':'csv','start':'2026-10-20T00:00:00Z','end':'2026-10-21T00:00:00Z'}).text)

    def test_password_recovery_revokes_old_sessions(self):
        c=dict(self.credentials,password='replacement-password-456',recovery_code=self.recovery)
        response=self.client.post('/api/auth/recover',json=c)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/sessions').status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json=self.credentials).status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json=c).status_code,200)
        self.assertEqual(self.client.post('/api/auth/recover',json=c).status_code,401)

    def test_account_deletion_and_request_guards(self):
        self.client.post('/api/sessions',json=movement())
        self.assertEqual(self.client.put('/api/profile',json={'name':'Other'},headers={'origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/health',headers={'host':'evil.example'}).status_code,400)
        result=self.client.request('DELETE','/api/auth/account',json={'confirmation':self.credentials['username'],'password':self.credentials['password']})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/sessions').status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json=self.credentials).status_code,401)

    def test_missing_providers_are_explicit(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'','GOOGLE_CLIENT_ID':'','GOOGLE_CLIENT_SECRET':''}):
            self.assertFalse(self.client.get('/api/auth/me').json()['chat'])
            self.assertEqual(self.client.post('/api/chat',json={'messages':[{'role':'user','content':'What is range?'}]}).json()['mode'],'help')
            self.assertEqual(self.client.get('/api/auth/google/start').status_code,503)

if __name__=='__main__':unittest.main()
