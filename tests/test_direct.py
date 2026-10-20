"""Socket-free verification for restricted environments.

Calls endpoints and middleware directly. This supplements, not replaces, HTTP tests.
"""
import copy
import json
import os
import sqlite3
import unittest
import uuid
from http.cookies import SimpleCookie
from pathlib import Path
from fastapi import HTTPException,Request,Response
from backend import submission_api as api
from backend.accounts import current_user
from backend.reports import report
from tests.test_platform import movement

def execute(coro):
    """Only for coroutines whose dependencies complete immediately in memory."""
    try:
        result=coro.send(None)
    except StopIteration as done:return done.value
    finally:
        if coro.cr_frame is not None:coro.close()
    raise AssertionError('Unexpected asynchronous I/O: '+repr(result))

def request(path='/',method='POST',headers=None,body=b''):
    async def receive():return {'type':'http.request','body':body,'more_body':False}
    return Request({'type':'http','method':method,'scheme':'http','path':path,'query_string':b'','server':('testserver',80),'client':('direct-'+uuid.uuid4().hex,50000),'headers':[(k.lower().encode(),v.encode()) for k,v in {'host':'testserver',**(headers or {})}.items()]},receive)

class DirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes={(method,r.path):r.endpoint for r in api.app.routes if hasattr(r,'methods') for method in r.methods}
        api.load_model()
    def endpoint(self,method,path):return self.routes[(method,path)]
    def account(self):
        credentials={'username':'direct_'+uuid.uuid4().hex[:12],'password':'test-password-123'}
        reg=self.endpoint('POST','/api/auth/register')(credentials,request())
        response=Response();u=self.endpoint('POST','/api/auth/login')(credentials,request(),response)
        cookie=SimpleCookie();cookie.load(response.headers['set-cookie'])
        with sqlite3.connect(os.environ['MOTIONAI_AUTH_DB']) as db:
            db.row_factory=sqlite3.Row;full=dict(db.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone())
        return credentials,reg['recovery_code'],full,cookie['motionai_session'].value
    def setUp(self):
        self.credentials,self.recovery,self.user,self.cookie=self.account()
        self.token=current_user.set(self.user)
    def tearDown(self):current_user.reset(self.token)
    def create(self,data=None):return api.create_session(data or movement())

    def test_isolated_accounts_and_identity_middleware(self):
        s=self.create();_,_,other,cookie=self.account();t=current_user.set(other)
        self.assertEqual(api.list_sessions(),[])
        with self.assertRaises(HTTPException) as e:api.read_session(s['id'])
        self.assertEqual(e.exception.status_code,404);current_user.reset(t)
        identity=next(m.cls for m in api.app.user_middleware if getattr(m,'kwargs',{}).get('dispatch',None) and m.kwargs['dispatch'].__name__=='identity')
        dispatch=next(m.kwargs['dispatch'] for m in api.app.user_middleware if m.kwargs.get('dispatch') and m.kwargs['dispatch'].__name__=='identity')
        async def accepted(req):return Response(current_user.get()['id'])
        denied=execute(dispatch(request('/api/sessions','GET'),accepted));self.assertEqual(denied.status_code,401)
        allowed=execute(dispatch(request('/api/sessions','GET',{'cookie':'motionai_session='+self.cookie}),accepted))
        self.assertEqual(allowed.body.decode(),self.user['id'])

    def test_reports_known_angles_and_visibility(self):
        s=movement();s['motionbert']=None;r=report(s)
        self.assertGreaterEqual(r['measured_cycles'],4)
        self.assertGreater(r['coverage'],90)
        self.assertGreater(r['metrics'][0]['value'],40)
        for f in s['frames']:f['metrics']['primary']=0
        self.assertEqual(report(s)['metrics'],r['metrics'])
        for f in s['frames']:
            for p in f['image']:p['visibility']=0
        missing=report(s)
        self.assertEqual(missing['coverage'],0)
        self.assertTrue(all(m['value'] is None for m in missing['metrics']))

    def test_upright_knee_bends_are_not_pushup_analysis(self):
        s=movement();s.update(exercise='push_up',motionbert=None)
        r=report(s)
        self.assertEqual(r['measured_cycles'],0)
        self.assertTrue(all(m['value'] is None for m in r['metrics']))

    def test_previous_two_sessions_and_trends(self):
        for day in (17,18,19):s=self.create(movement(f'2026-10-{day}T12:00:00Z'))
        r=self.endpoint('GET','/api/sessions/{session_id}/report')(s['id'])
        self.assertEqual(len(r['comparison']['previous']),2)
        self.assertEqual(r['comparison']['changes'][0]['delta'],0)
        trends=self.endpoint('GET','/api/trends')('squat','range','camera')
        self.assertEqual(len(trends),3)

    def test_backup_deduplication_and_untrusted_model(self):
        self.create();export=self.endpoint('GET','/api/export');backup=export()
        preview=self.endpoint('POST','/api/import/preview')(backup)
        self.assertEqual(preview['duplicates'],1)
        _,_,other,_=self.account();t=current_user.set(other)
        backup['sessions'][0]['motionbert']={'frames':[[999]]}
        imported=self.endpoint('POST','/api/import')(backup)
        self.assertEqual(imported['sessions'],1)
        self.assertIsNone(api.read_session(api.list_sessions()[0]['id'])['motionbert'])
        self.assertEqual(self.endpoint('POST','/api/import')(backup)['duplicates'],1)
        current_user.reset(t)

    def test_routine_backup_roundtrip_and_csv(self):
        r=self.endpoint('POST','/api/routines')({'id':str(uuid.uuid4()),'template':'standing'})
        update=self.endpoint('PATCH','/api/routines/{run_id}');update(r['id'],{'step':0,'status':'done'})
        step=r['steps'][1];s=movement();s.update(exercise=step['exercise'],client_id=step['recording_id'],source='camera');self.create(s)
        update(r['id'],{'finish':True})
        backup=self.endpoint('GET','/api/export')(routine_id=r['id'])
        _,_,other,_=self.account();t=current_user.set(other)
        self.assertEqual(self.endpoint('POST','/api/import')(backup)['routines'],1)
        run=self.endpoint('GET','/api/routines')()[0]
        self.assertEqual(run['steps'][0]['duration'],30)
        self.assertEqual(api.read_session(run['steps'][1]['session_id'])['exercise'],'shoulder_press')
        self.assertEqual(self.endpoint('POST','/api/import')(backup)['routines'],0)
        csv=self.endpoint('GET','/api/export')(format='csv').body.decode()
        self.assertIn('range_degrees',csv);self.assertIn('Shoulder press',csv)
        current_user.reset(t)

    def test_recovery_and_account_deletion(self):
        s=self.create();folder=Path(os.environ['MOTIONAI_USER_DATA_DIR']);path=folder/(self.user['id']+'.sqlite');self.assertTrue(path.exists())
        changed={**self.credentials,'password':'changed-password-456','recovery_code':self.recovery}
        self.endpoint('POST','/api/auth/recover')(changed,request())
        with sqlite3.connect(os.environ['MOTIONAI_AUTH_DB']) as db:self.assertEqual(db.execute('SELECT count(*) FROM logins WHERE user_id=?',(self.user['id'],)).fetchone()[0],0)
        with self.assertRaises(HTTPException):self.endpoint('POST','/api/auth/login')(self.credentials,request(),Response())
        self.endpoint('POST','/api/auth/login')(changed,request(),Response())
        # Context is refreshed per request in normal operation.
        with sqlite3.connect(os.environ['MOTIONAI_AUTH_DB']) as db:
            db.row_factory=sqlite3.Row;u=dict(db.execute('SELECT * FROM users WHERE id=?',(self.user['id'],)).fetchone())
        current_user.set(u)
        self.endpoint('DELETE','/api/auth/account')({'confirmation':u['username'],'password':changed['password']},request(),Response())
        self.assertFalse(path.exists())

    def test_request_guards_and_upload_validation(self):
        async def accepted(req):return Response('accepted')
        for headers,status in [({'origin':'https://other.example'},403),({'host':'evil.example'},400),({'content-length':'30000001'},413),({'content-length':'invalid'},400)]:
            response=execute(api.local_requests(request('/api/sessions',headers=headers),accepted));self.assertEqual(response.status_code,status)
        self.assertEqual(execute(api.local_requests(request('/api/profile',headers={'content-length':'2'},body=b'{}'),accepted)).status_code,200)
        bad=movement();bad['frames'][-1]['timestamp']=100000
        with self.assertRaises(HTTPException):api.validate_session(bad)
        backup={'format':'motionai-backup','version':99,'sessions':[]}
        with self.assertRaises(HTTPException):self.endpoint('POST','/api/import/preview')(backup)

    def test_real_motionbert_output_drives_report(self):
        self.assertIsNotNone(api.model,api.model_error)
        self.assertEqual(api.parameters,16001549)
        s=self.create();analysed=api.analyze_session(s['id'])
        self.assertEqual(len(analysed['motionbert']['frames']),len(s['frames']))
        self.assertEqual(report(analysed)['source'],'MotionBERT 3D')
        self.assertEqual(analysed['motionbert']['checkpoint_sha256'],'9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f')
        self.assertEqual(api.analyze_session(s['id'])['motionbert'],analysed['motionbert'])

if __name__=='__main__':unittest.main()
