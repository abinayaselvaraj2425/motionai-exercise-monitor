"""Socket-free checks for hosted settings, request guards, profile input and chat."""
import base64
import json
import os
import sqlite3
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs,urlsplit
import unittest
from unittest.mock import patch
from fastapi import HTTPException,Response
from backend import submission_api as api
from backend.accounts import current_user
from backend.deployment import validate_deployment,google_redirect,allowed_hosts,secure_cookies
from tests.test_direct import execute,request

class DeploymentTests(unittest.TestCase):
    def test_production_configuration_rejects_missing_origin_and_http(self):
        with patch.dict(os.environ,{'MOTIONAI_ENV':'production'},clear=True):
            with self.assertRaises(ValueError):validate_deployment()
        with patch.dict(os.environ,{'MOTIONAI_ENV':'production','MOTIONAI_PUBLIC_URL':'http://motion.example'},clear=True):
            with self.assertRaises(ValueError):validate_deployment()

    def test_hosted_configuration_and_derived_callback(self):
        with patch.dict(os.environ,{'MOTIONAI_ENV':'production','MOTIONAI_PUBLIC_URL':'https://motion.example','MOTIONAI_AUTH_DB':'/var/data/accounts.sqlite','MOTIONAI_USER_DATA_DIR':'/var/data/users','MOTIONAI_DB':'/var/data/system.sqlite'},clear=True):
            # Windows sees /var/data as rooted rather than absolute; use native test paths.
            for key in ('MOTIONAI_AUTH_DB','MOTIONAI_USER_DATA_DIR','MOTIONAI_DB'):os.environ[key]=os.path.abspath(os.environ[key])
            validate_deployment()
            self.assertTrue(secure_cookies())
            self.assertEqual(google_redirect(),'https://motion.example/api/auth/google/callback')
            self.assertEqual(allowed_hosts(),{'motion.example'})
            os.environ['GOOGLE_CLIENT_ID']='example';os.environ['GOOGLE_CLIENT_SECRET']='secret';os.environ['GOOGLE_REDIRECT_URI']='https://other.example/callback'
            with self.assertRaises(ValueError):validate_deployment()

    def test_local_port_selects_correct_google_callback(self):
        with patch.dict(os.environ,{'MOTIONAI_PORT':'3001'},clear=True):self.assertEqual(google_redirect(),'http://localhost:3001/api/auth/google/callback')

    def test_render_origin_can_be_derived_without_guessing_a_domain(self):
        with patch.dict(os.environ,{'MOTIONAI_ENV':'production','RENDER_EXTERNAL_URL':'https://motion-example.onrender.com','RENDER_EXTERNAL_HOSTNAME':'motion-example.onrender.com'},clear=True):
            self.assertEqual(google_redirect(),'https://motion-example.onrender.com/api/auth/google/callback')
            self.assertEqual(allowed_hosts(),{'motion-example.onrender.com'})

    def test_hosted_https_origin_works_behind_http_proxy(self):
        async def accepted(req):return Response('okay')
        with patch.dict(os.environ,{'MOTIONAI_PUBLIC_URL':'https://motion.example','MOTIONAI_ALLOWED_HOSTS':'motion.example'}):
            response=execute(api.local_requests(request('/api/profile',headers={'host':'motion.example','origin':'https://motion.example','content-length':'2'},body=b'{}'),accepted))
            self.assertEqual(response.status_code,200)
            response=execute(api.local_requests(request('/api/profile',headers={'host':'motion.example','origin':'https://evil.example'}),accepted))
            self.assertEqual(response.status_code,403)

    def test_production_responses_have_browser_security_headers(self):
        identity=next(m.kwargs['dispatch'] for m in api.app.user_middleware if m.kwargs.get('dispatch').__name__=='identity')
        async def accepted(req):return Response('okay')
        with patch.dict(os.environ,{'MOTIONAI_ENV':'production'}):
            response=execute(identity(request('/api/health',method='GET'),accepted))
        self.assertIn('max-age=',response.headers['strict-transport-security'])
        self.assertIn("frame-ancestors 'none'",response.headers['content-security-policy'])
        self.assertIn('camera=(self)',response.headers['permissions-policy'])

    def test_profile_rejects_external_or_mislabeled_images_and_duplicate_widgets(self):
        for avatar in ['https://example.com/photo.png','data:image/svg+xml;base64,PHN2Zz4=','data:image/png;base64,'+base64.b64encode(b'not a png').decode()]:
            with self.subTest(avatar=avatar):
                with self.assertRaises(HTTPException):api.update_profile(api.ProfileInput(name='Test',avatar=avatar))
        with self.assertRaises(HTTPException):api.update_profile(api.ProfileInput(name='Test',homeWidgets=['reports','reports']))

    def test_chat_help_never_contacts_provider_and_does_not_invent_context(self):
        endpoint=next(r.endpoint for r in api.app.routes if getattr(r,'path','')=='/api/chat')
        token=current_user.set({'id':'help-test'})
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':''}),patch('backend.assistant.httpx.AsyncClient',side_effect=AssertionError('Unexpected network')):
                result=execute(endpoint({'messages':[{'role':'user','content':'How are reps counted?'}]}))
                self.assertEqual(result['mode'],'help');self.assertIn('starting position',result['answer'])
                result=execute(endpoint({'messages':[{'role':'user','content':'Explain my report'}]}))
                self.assertIn('enable',result['answer']);self.assertFalse(result['included_session'])
        finally:current_user.reset(token)

    def test_connected_chat_sends_correct_schema_and_handles_provider_failure(self):
        endpoint=next(r.endpoint for r in api.app.routes if getattr(r,'path','')=='/api/chat')
        calls=[]
        class Provider:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return False
            async def post(self,url,**kwargs):
                calls.append((url,kwargs))
                class Reply:
                    def raise_for_status(self):pass
                    def json(self):return {'output':[{'type':'message','content':[{'type':'output_text','text':'A clear answer.'}]}]}
                return Reply()
        token=current_user.set({'id':'ai-test'})
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key','OPENAI_MODEL':'test-model'}),patch('backend.assistant.httpx.AsyncClient',Provider):
                # Factory accepts provider timeout without performing I/O.
                with patch('backend.assistant.httpx.AsyncClient',lambda **kw:Provider()):
                    result=execute(endpoint({'messages':[{'role':'user','content':'Explain range'}]}))
            self.assertEqual(result['answer'],'A clear answer.')
            self.assertFalse(calls[0][1]['json']['store']);self.assertEqual(calls[0][1]['json']['model'],'test-model')
            self.assertNotIn('analysis',calls[0][1]['json']['instructions'].split('Context: ')[1])
        finally:current_user.reset(token)

    def test_google_authorization_roundtrip_checks_pkce_and_identity(self):
        routes={r.path:r.endpoint for r in api.app.routes if hasattr(r,'path')}
        with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'client-id','GOOGLE_CLIENT_SECRET':'secret','MOTIONAI_PUBLIC_URL':'https://motion.example','GOOGLE_REDIRECT_URI':''}):
            response=routes['/api/auth/google/start'](request())
            query=parse_qs(urlsplit(response.headers['location']).query)
            state=query['state'][0]
            self.assertEqual(query['code_challenge_method'],['S256'])
            self.assertEqual(query['redirect_uri'],['https://motion.example/api/auth/google/callback'])
            with sqlite3.connect(os.environ['MOTIONAI_AUTH_DB']) as db:
                nonce=db.execute('SELECT nonce FROM oauth WHERE state=?',(api.hashlib.sha256(state.encode()).hexdigest(),)).fetchone()[0]
            claims={'sub':'google-test-subject','iss':'https://accounts.google.com','aud':'client-id','exp':time.time()+120,'nonce':nonce}
            token='header.'+base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')+'.signature'
            class Provider:
                async def __aenter__(self):return self
                async def __aexit__(self,*args):return False
                async def post(self,url,**kw):
                    selftest.assertIn('code_verifier',kw['data'])
                    class Reply:
                        def raise_for_status(self):pass
                        def json(self):return {'id_token':token}
                    return Reply()
            selftest=self
            with patch('backend.accounts.httpx.AsyncClient',lambda **kw:Provider()):
                result=execute(routes['/api/auth/google/callback'](request(headers={'cookie':'motionai_oauth='+state}),code='provider-code',state=state))
            self.assertEqual(result.headers['location'],'/')
            self.assertTrue(any('motionai_session=' in value for value in result.headers.getlist('set-cookie')))
            with self.assertRaises(HTTPException):execute(routes['/api/auth/google/callback'](request(headers={'cookie':'motionai_oauth='+state}),code='provider-code',state=state))

    def test_ai_provider_authentication_error_has_no_secret_in_message(self):
        import httpx
        endpoint=next(r.endpoint for r in api.app.routes if getattr(r,'path','')=='/api/chat')
        class Provider:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return False
            async def post(self,*a,**kw):
                req=httpx.Request('POST','https://api.openai.com/v1/responses')
                response=httpx.Response(401,request=req)
                raise httpx.HTTPStatusError('private-provider-message',request=req,response=response)
        token=current_user.set({'id':'provider-error-test'})
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'never-expose-this'}),patch('backend.assistant.httpx.AsyncClient',lambda **kw:Provider()):
                with self.assertRaises(HTTPException) as error:execute(endpoint({'messages':[{'role':'user','content':'Hello'}]}))
            self.assertEqual(error.exception.status_code,503)
            self.assertNotIn('never-expose-this',error.exception.detail)
        finally:current_user.reset(token)

if __name__=='__main__':unittest.main()
