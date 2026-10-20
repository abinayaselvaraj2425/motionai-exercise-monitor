"""Keep automated account and session fixtures separate from real user data."""
import os
import uuid
from pathlib import Path
_root=Path(__file__).parent/'.test-data'/str(uuid.uuid4())
_root.mkdir(parents=True,exist_ok=True)
os.environ['MOTIONAI_AUTH_DB']=str(_root/'accounts.sqlite')
os.environ['MOTIONAI_USER_DATA_DIR']=str(_root/'users')

def sign_in(client):
    username='test_'+uuid.uuid4().hex[:16]
    credentials={'username':username,'password':'test-password-123'}
    registered=client.post('/api/auth/register',json=credentials)
    assert registered.status_code==201,registered.text
    signed=client.post('/api/auth/login',json=credentials)
    assert signed.status_code==200,signed.text
    return credentials,registered.json()['recovery_code']
