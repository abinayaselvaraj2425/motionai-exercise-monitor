"""Small explicit .env loader; never executes configuration as shell or Python code."""
import os

ALLOWED={'GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REDIRECT_URI','OPENAI_API_KEY','OPENAI_MODEL','MOTIONAI_SECURE_COOKIES','MOTIONAI_ALLOWED_HOSTS','MOTIONAI_PORT','MOTIONAI_ENV','MOTIONAI_PUBLIC_URL','MOTIONAI_AUTH_DB','MOTIONAI_USER_DATA_DIR','MOTIONAI_DB','MOTIONAI_REQUIRE_MODEL','FORWARDED_ALLOW_IPS'}

def load_configuration(root):
    path=root/'.env'
    if not path.is_file():return
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in ALLOWED:continue
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
        os.environ.setdefault(key,value)
