"""Explicit local/hosted configuration; never derive public URLs from client headers."""
import os
from pathlib import Path
from urllib.parse import urlsplit

def production():return os.getenv('MOTIONAI_ENV','local').strip().lower()=='production'

def public_url():
    value=(os.getenv('MOTIONAI_PUBLIC_URL','').strip() or os.getenv('RENDER_EXTERNAL_URL','').strip()).rstrip('/')
    if not value:
        if production():raise ValueError('Set MOTIONAI_PUBLIC_URL to your HTTPS website address.')
        return ''
    url=urlsplit(value)
    if url.scheme not in ('https','http') or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError('MOTIONAI_PUBLIC_URL must be an origin, for example https://motionai.example.com.')
    if production() and url.scheme!='https':raise ValueError('Production requires an HTTPS public URL.')
    return value

def secure_cookies():return production() or os.getenv('MOTIONAI_SECURE_COOKIES')=='1'

def allowed_hosts():
    origin=public_url()
    defaults='' if production() else 'localhost,127.0.0.1,::1,testserver'
    hosts={v.strip().lower() for v in os.getenv('MOTIONAI_ALLOWED_HOSTS',defaults).split(',') if v.strip()}
    if origin:hosts.add(urlsplit(origin).hostname.lower())
    render_host=os.getenv('RENDER_EXTERNAL_HOSTNAME','').strip().lower()
    if render_host:hosts.add(render_host)
    if '*' in hosts:raise ValueError('List explicit allowed hostnames instead of a wildcard.')
    return hosts

def google_redirect():
    configured=os.getenv('GOOGLE_REDIRECT_URI','').strip()
    return configured or (public_url() or 'http://localhost:'+os.getenv('MOTIONAI_PORT','3000'))+'/api/auth/google/callback'

def validate_deployment():
    origin=public_url();allowed_hosts()
    if production():
        if os.getenv('MOTIONAI_REQUIRE_MODEL','1') not in ('0','1'):raise ValueError('MOTIONAI_REQUIRE_MODEL must be 0 or 1.')
        for key in ('MOTIONAI_AUTH_DB','MOTIONAI_USER_DATA_DIR','MOTIONAI_DB'):
            if not os.getenv(key) or not Path(os.environ[key]).is_absolute():raise ValueError(f'Set {key} to an absolute persistent-storage path.')
        if os.getenv('GOOGLE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_SECRET'):
            if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):raise ValueError('Google sign-in requires both client ID and client secret.')
            if google_redirect()!=origin+'/api/auth/google/callback':raise ValueError('Google redirect must match your public URL plus /api/auth/google/callback.')
