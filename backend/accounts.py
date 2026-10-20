"""Local accounts, opaque sessions, recovery codes and Google authorization-code sign-in."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

current_user = ContextVar('motionai_user', default=None)
COOKIE = 'motionai_session'

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def verify(password, stored):
    return bool(stored) and hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)

def register_accounts(app, root):
    account_path = Path(os.environ.get('MOTIONAI_AUTH_DB', str(root / 'data' / 'accounts.sqlite')))
    @contextmanager
    def accounts():
        path=Path(os.environ.get('MOTIONAI_AUTH_DB',str(account_path)))
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=30)
        db.row_factory = sqlite3.Row
        db.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE, password TEXT, recovery TEXT, google_sub TEXT UNIQUE);
          CREATE TABLE IF NOT EXISTS logins(token TEXT PRIMARY KEY, user_id TEXT, expires REAL);
          CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY, count INTEGER, expires REAL);
          CREATE TABLE IF NOT EXISTS oauth(state TEXT PRIMARY KEY, nonce TEXT, verifier TEXT, expires REAL);''')
        try:
            with db: yield db
        finally: db.close()

    def limited(request, category):
        key = category + ':' + (request.client.host if request.client else 'local')
        with accounts() as db:
            db.execute('DELETE FROM attempts WHERE expires < ?', (time.time(),))
            row = db.execute('SELECT count FROM attempts WHERE key=?', (key,)).fetchone()
            if row and row[0] >= 20: raise HTTPException(429, 'Too many attempts. Please wait 15 minutes.')
            db.execute('INSERT INTO attempts VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, 1, time.time()+900))

    def public(user): return {'id': user['id'], 'username': user['username'], 'provider': 'google' if user['google_sub'] else 'password'}
    def issue(user, response):
        token = secrets.token_urlsafe(32)
        with accounts() as db:
            db.execute('DELETE FROM logins WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO logins VALUES (?,?,?)', (digest(token), user['id'], time.time()+7*86400))
        response.set_cookie(COOKIE, token, httponly=True, samesite='lax', secure=os.getenv('MOTIONAI_SECURE_COOKIES') == '1', max_age=7*86400)
        return public(user)

    @app.middleware('http')
    async def identity(request, call_next):
        user = None
        token = request.cookies.get(COOKIE)
        if token:
            with accounts() as db:
                user = db.execute('SELECT users.* FROM users JOIN logins ON users.id=logins.user_id WHERE token=? AND expires>?', (digest(token),time.time())).fetchone()
        ctx = current_user.set(dict(user) if user else None)
        try:
            if request.url.path.startswith('/api/') and request.url.path != '/api/health' and not request.url.path.startswith('/api/auth/') and not user:
                return JSONResponse({'detail':'Please sign in to continue.'}, status_code=401)
            response = await call_next(request)
            if request.url.path.startswith('/api/'):
                response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'same-origin'
            response.headers['X-Frame-Options'] = 'DENY'
            return response
        finally: current_user.reset(ctx)

    @app.get('/api/auth/me')
    def me():
        u = current_user.get()
        return {'user': public(u) if u else None, 'google': bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')), 'chat': bool(os.getenv('OPENAI_API_KEY'))}

    def credentials(data):
        name, password = data.get('username',''), data.get('password','')
        if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}',name):
            raise HTTPException(422, 'Use 3–40 letters, numbers, dots, hyphens or underscores for your username.')
        if not isinstance(password,str) or not 10 <= len(password) <= 128:
            raise HTTPException(422, 'Use a password between 10 and 128 characters.')
        return name.lower(), password

    @app.post('/api/auth/register', status_code=201)
    def register(data:dict, request:Request):
        limited(request,'register')
        name,pw = credentials(data)
        recovery=secrets.token_urlsafe(24)
        try:
            with accounts() as db:
                db.execute('INSERT INTO users VALUES (?,?,?,?,NULL)',(str(uuid.uuid4()),name,password_hash(pw),digest(recovery)))
        except sqlite3.IntegrityError: raise HTTPException(409,'That username is already taken.')
        return {'username':name,'recovery_code':recovery}

    @app.post('/api/auth/login')
    def login(data:dict, request:Request, response:Response):
        limited(request,'login')
        name,pw=credentials(data)
        with accounts() as db: u=db.execute('SELECT * FROM users WHERE username=?',(name,)).fetchone()
        # Always perform a password derivation, including for an unknown user.
        valid=verify(pw,u['password'] if u and u['password'] else '00'*16+':'+'00'*64)
        if not u or not valid: raise HTTPException(401,'Username or password is incorrect.')
        return issue(u,response)

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        with accounts() as db: db.execute('DELETE FROM logins WHERE token=?',(digest(request.cookies.get(COOKIE,'')),))
        response.delete_cookie(COOKIE)
        return {'ok':True}

    @app.post('/api/auth/recover')
    def recover(data:dict, request:Request):
        limited(request,'recovery')
        name,pw=credentials(data)
        code=data.get('recovery_code','')
        if not isinstance(code,str) or len(code)>200: raise HTTPException(422,'Invalid recovery code.')
        replacement=secrets.token_urlsafe(24)
        with accounts() as db:
            u=db.execute('SELECT * FROM users WHERE username=?',(name,)).fetchone()
            if not u or not u['recovery'] or not hmac.compare_digest(digest(code),u['recovery']): raise HTTPException(401,'Username or recovery code is incorrect.')
            db.execute('UPDATE users SET password=?,recovery=? WHERE id=?',(password_hash(pw),digest(replacement),u['id']))
            db.execute('DELETE FROM logins WHERE user_id=?',(u['id'],))
        return {'username':name,'recovery_code':replacement}

    @app.delete('/api/auth/account')
    def delete_account(data:dict,request:Request,response:Response):
        u=current_user.get()
        if not u: raise HTTPException(401,'Sign in first.')
        limited(request,'delete')
        if data.get('confirmation') != u['username']: raise HTTPException(422,'Type your username to confirm deletion.')
        if u['password'] and not verify(str(data.get('password','')),u['password']): raise HTTPException(401,'Password is incorrect.')
        with accounts() as db:
            db.execute('DELETE FROM logins WHERE user_id=?',(u['id'],))
            db.execute('DELETE FROM users WHERE id=?',(u['id'],))
        # User IDs are server-generated UUIDs; never accept filesystem paths from requests.
        folder=Path(os.environ.get('MOTIONAI_USER_DATA_DIR',str(root/'data'/'users')))
        for suffix in ('','.sqlite-wal','.sqlite-shm'):
            path=folder/(u['id']+'.sqlite') if not suffix else folder/(u['id']+suffix)
            path.unlink(missing_ok=True)
        response.delete_cookie(COOKIE)
        return {'deleted':True}

    @app.get('/api/auth/google/start')
    def google_start():
        if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'): raise HTTPException(503,'Google sign-in is not configured yet. Use a username and password.')
        state,nonce,verifier=[secrets.token_urlsafe(32) for _ in range(3)]
        with accounts() as db:
            db.execute('DELETE FROM oauth WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO oauth VALUES (?,?,?,?)',(digest(state),nonce,verifier,time.time()+600))
        redirect=os.getenv('GOOGLE_REDIRECT_URI','http://localhost:3000/api/auth/google/callback')
        query=urlencode(dict(client_id=os.environ['GOOGLE_CLIENT_ID'],redirect_uri=redirect,response_type='code',scope='openid email profile',state=state,nonce=nonce,code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),code_challenge_method='S256'))
        response=RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+query)
        response.set_cookie('motionai_oauth',state,httponly=True,samesite='lax',secure=os.getenv('MOTIONAI_SECURE_COOKIES')=='1',max_age=600)
        return response

    @app.get('/api/auth/google/callback')
    async def google_callback(request:Request,code:str='',state:str=''):
        if not state or not hmac.compare_digest(state,request.cookies.get('motionai_oauth','')): raise HTTPException(400,'Google sign-in expired. Try again.')
        with accounts() as db:
            row=db.execute('SELECT * FROM oauth WHERE state=? AND expires>?',(digest(state),time.time())).fetchone()
            db.execute('DELETE FROM oauth WHERE state=?',(digest(state),))
        if not row: raise HTTPException(400,'Google sign-in expired. Try again.')
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                result=await client.post('https://oauth2.googleapis.com/token',data=dict(code=code,client_id=os.environ['GOOGLE_CLIENT_ID'],client_secret=os.environ['GOOGLE_CLIENT_SECRET'],redirect_uri=os.getenv('GOOGLE_REDIRECT_URI','http://localhost:3000/api/auth/google/callback'),grant_type='authorization_code',code_verifier=row['verifier']))
                result.raise_for_status()
                token=result.json()['id_token']
                # Token comes directly from Google's TLS token endpoint; validate all identity claims.
                part=token.split('.')[1]
                claims=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
                if claims.get('iss') not in ('accounts.google.com','https://accounts.google.com') or claims.get('aud')!=os.environ['GOOGLE_CLIENT_ID'] or claims.get('exp',0)<=time.time() or claims.get('nonce')!=row['nonce'] or not claims.get('sub'): raise ValueError('Invalid claims')
        except Exception: return RedirectResponse('/?auth_error=google')
        with accounts() as db:
            u=db.execute('SELECT * FROM users WHERE google_sub=?',(claims['sub'],)).fetchone()
            if not u:
                uid=str(uuid.uuid4())
                db.execute('INSERT INTO users VALUES (?,?,NULL,NULL,?)',(uid,'athlete_'+uid[:8],claims['sub']))
                u=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        response=RedirectResponse('/')
        response.delete_cookie('motionai_oauth')
        issue(u,response)
        return response
