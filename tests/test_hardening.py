"""Regression checks for security boundaries and tracking gaps; no live providers."""
import copy
import os
import unittest
import uuid
from unittest.mock import patch
from fastapi import HTTPException, Response
from backend import submission_api as api
from backend.accounts import current_user
from backend.reports import report
from tests.test_direct import execute, request
from tests.test_platform import movement

class HardeningTests(unittest.TestCase):
    def endpoint(self,path):
        return next(r.endpoint for r in api.app.routes if getattr(r,'path','')==path)

    def test_cross_site_write_without_origin_is_rejected(self):
        async def accept(req): return Response('ok')
        reply=execute(api.local_requests(request('/api/profile',headers={'sec-fetch-site':'cross-site'}),accept))
        self.assertEqual(reply.status_code,403)

    def test_chat_body_limit_checks_actual_bytes(self):
        async def accept(req): self.fail('Oversized body reached endpoint')
        reply=execute(api.local_requests(request('/api/chat',body=b'x'*100001),accept))
        self.assertEqual(reply.status_code,413)

    def test_unauthenticated_response_is_not_cacheable(self):
        identity=next(m.kwargs['dispatch'] for m in api.app.user_middleware if m.kwargs.get('dispatch').__name__=='identity')
        async def accept(req): self.fail('Anonymous request reached endpoint')
        reply=execute(identity(request('/api/sessions',method='GET'),accept))
        self.assertEqual(reply.status_code,401)
        self.assertEqual(reply.headers['cache-control'],'no-store')
        self.assertEqual(reply.headers['x-content-type-options'],'nosniff')

    def test_login_account_limit_survives_ip_changes(self):
        login=self.endpoint('/api/auth/login')
        credentials={'username':'limit_'+uuid.uuid4().hex[:16],'password':'test-password-123'}
        for _ in range(20):
            with self.assertRaises(HTTPException) as error: login(credentials,request(),Response())
            self.assertEqual(error.exception.status_code,401)
        with self.assertRaises(HTTPException) as error: login(credentials,request(),Response())
        self.assertEqual(error.exception.status_code,429)

    def test_conversation_budget_is_checked_before_provider_call(self):
        chat=self.endpoint('/api/chat')
        with self.assertRaises(HTTPException) as error:
            execute(chat({'messages':[{'role':'user','content':'x'*3000} for _ in range(5)]}))
        self.assertEqual(error.exception.status_code,422)

    def test_followup_accepts_a_long_assistant_reply(self):
        ctx=current_user.set({'id':uuid.uuid4().hex})
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
                result=execute(self.endpoint('/api/chat')({'messages':[{'role':'assistant','content':'x'*5000},{'role':'user','content':'Explain range'}]}))
            self.assertEqual(result['mode'],'help')
        finally:current_user.reset(ctx)

    def test_chat_strips_provider_fields_and_requires_session_consent(self):
        calls=[]
        class Provider:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def post(self,url,**kw):
                calls.append(kw['json'])
                class Reply:
                    def raise_for_status(self):pass
                    def json(self):return {'output':[{'type':'message','content':[{'type':'output_text','text':'Hello'}]}]}
                return Reply()
        ctx=current_user.set({'id':uuid.uuid4().hex})
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch('backend.assistant.httpx.AsyncClient',lambda **kw:Provider()):
                execute(self.endpoint('/api/chat')({'messages':[{'role':'user','content':'Hi','tool_calls':[{'secret':'ignored'}]}],'session_id':'not-shared'}))
            self.assertEqual(calls[0]['input'],[{'role':'user','content':'Hi'}])
            self.assertNotIn('not-shared',calls[0]['instructions'])
        finally:current_user.reset(ctx)

    def test_busy_analysis_returns_retry_instead_of_queueing(self):
        with api.analysis_slot():
            with self.assertRaises(HTTPException) as error:
                with api.analysis_slot(): self.fail('Concurrent job entered')
            self.assertEqual(error.exception.status_code,429)
        with api.analysis_slot():pass

    def test_tracking_gap_contributes_no_measured_time(self):
        session=movement()
        # Two short continuous fragments, separated by a long camera gap.
        session['frames']=copy.deepcopy(session['frames'][:6]+session['frames'][-6:])
        result=report(session)
        self.assertLessEqual(result['coverage'],11)

    def test_slow_sampling_is_not_automatically_low_coverage(self):
        session=movement()
        session['frames']=session['frames'][::5] # 2fps; no gap over 650ms
        result=report(session)
        self.assertGreaterEqual(result['coverage'],95)

if __name__=='__main__':unittest.main()
