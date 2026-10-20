"""Local project API: SQLite persistence, validated camera data, real MotionBERT lifting."""
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
from functools import partial
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from backend.accounts import current_user, register_accounts

ROOT = Path(__file__).resolve().parent.parent
from backend.configuration import load_configuration
load_configuration(ROOT)
from backend.deployment import production, public_url, allowed_hosts, validate_deployment
DB_PATH = Path(os.environ.get('MOTIONAI_DB', str(ROOT / 'data' / 'motionai.sqlite')))
CHECKPOINT = ROOT / 'models' / 'motionbert' / 'best_epoch.bin'
EXERCISES = {'squat', 'lunge', 'push_up', 'jumping_jack', 'shoulder_press'}
model = None
model_error = 'Model is starting.'
model_hash = None
parameters = 0
lock = threading.Lock()
model_load_lock = threading.Lock()
@contextmanager
def analysis_slot():
    # Avoid filling the request worker pool with long-running queued model jobs.
    if not lock.acquire(blocking=False):
        raise HTTPException(429, 'Another analysis is running. Please try again shortly.', headers={'Retry-After':'5'})
    try:
        yield
    finally:
        lock.release()
model_state = 'loading'
logger = logging.getLogger('motionai')
CAMERA_FILES = {
    'pose_model': 'mediapipe/pose_landmarker_lite.task',
    'wasm_loader': 'mediapipe/wasm/vision_wasm_internal.js',
    'wasm_binary': 'mediapipe/wasm/vision_wasm_internal.wasm',
    'wasm_fallback_loader': 'mediapipe/wasm/vision_wasm_nosimd_internal.js',
    'wasm_fallback_binary': 'mediapipe/wasm/vision_wasm_nosimd_internal.wasm',
}

def camera_assets():
    files = {name: (ROOT / 'dist' / relative).is_file() and (ROOT / 'dist' / relative).stat().st_size > 0 for name, relative in CAMERA_FILES.items()}
    return {'ready': all(files.values()), 'files': files, 'missing': [CAMERA_FILES[name] for name, present in files.items() if not present]}

@contextmanager
def database():
    user = current_user.get()
    path = Path(os.environ.get('MOTIONAI_USER_DATA_DIR',str(ROOT / 'data' / 'users'))) / (user['id'] + '.sqlite') if user else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, date TEXT NOT NULL, payload TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    try:
        with connection:
            yield connection
    finally:
        connection.close()

def load_model():
    # Live camera tracking runs in the browser and must not wait for Torch to start.
    with model_load_lock:
        _load_model()

def _load_model():
    global model, model_error, model_hash, parameters, model_state
    model_state = 'loading'
    model_error = 'MotionBERT is loading. Live camera tracking is available.'
    model = None
    parameters = 0
    model_hash = None
    try:
        import torch
        import torch.nn as nn
        from backend.motionbert.model import DSTformer
        if not CHECKPOINT.is_file():
            raise FileNotFoundError('MotionBERT checkpoint not configured. Run the checkpoint downloader.')
        verified_hash = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
        if verified_hash != '9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f':
            raise ValueError('MotionBERT checkpoint checksum does not match the official verified file.')
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        candidate = DSTformer(dim_in=3, dim_out=3, dim_feat=256, dim_rep=512, depth=5, num_heads=8, mlp_ratio=4, norm_layer=partial(nn.LayerNorm, eps=1e-6), maxlen=243, num_joints=17, att_fuse=True)
        # Official checkpoint contains a state dictionary plus training metadata.
        checkpoint = torch.load(CHECKPOINT, map_location='cpu', weights_only=True)
        weights = checkpoint.get('model_pos', checkpoint.get('state_dict', checkpoint))
        weights = {key.removeprefix('module.'): value for key, value in weights.items()}
        # Reject partial/mismatched weights; never run with randomly initialized missing layers.
        candidate.load_state_dict(weights, strict=True)
        candidate.eval()
        model_hash = verified_hash
        parameters = sum(p.numel() for p in candidate.parameters())
        model = candidate
        model_error = None
        model_state = 'ready'
    except Exception as exc:
        model = None
        model_error = str(exc)
        model_state = 'unavailable'
        logger.warning('MotionBERT is unavailable: %s', exc)

@asynccontextmanager
async def lifespan(app):
    validate_deployment()
    with database() as db:
        db.execute('PRAGMA journal_mode=WAL')
    threading.Thread(target=load_model, name='motionbert-loader', daemon=True).start()
    yield

app = FastAPI(title='MotionAI Exercise Monitoring', version='2.0.0', lifespan=lifespan)
register_accounts(app, ROOT)

@app.middleware('http')
async def local_requests(request: Request, call_next):
    allowed = allowed_hosts()
    local_probe=request.url.path=='/healthz' and request.url.hostname in ('localhost','127.0.0.1','::1')
    if request.url.hostname not in allowed and not local_probe:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={'detail':'This host is not allowed.'})
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        if request.headers.get('sec-fetch-site')=='cross-site':
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403,content={'detail':'Use the app from its own website address.'})
        origin = request.headers.get('origin')
        if origin and origin != (public_url() or f"{request.url.scheme}://{request.headers.get('host')}"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={'detail':'Use the app from its own website address.'})
        try:
            length = int(request.headers.get('content-length', '0'))
            if length < 0:
                raise ValueError()
        except ValueError:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={'detail':'Invalid upload length.'})
        limit = 100_000 if request.url.path.startswith('/api/auth/') or request.url.path=='/api/chat' else 30_000_000
        if length > limit:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=413, content={'detail':'Request is too large for this endpoint.'})
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>limit:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=413,content={'detail':'Request is too large for this endpoint.'})
            chunks.append(chunk)
        request._body=b''.join(chunks)
    return await call_next(request)

class ProfileInput(BaseModel):
    name: str = Field(default='Athlete', min_length=1, max_length=40)
    weeklyGoal: int = Field(default=3, ge=1, le=14)
    repTarget: int = Field(default=10, ge=1, le=100)
    audio: bool = True
    goal: str = Field(default='Build a movement habit', max_length=100)
    onboarded: bool = False
    reducedMotion: bool = False
    theme: str = Field(default='light', pattern='^(system|light|dark)$')
    avatar: str = Field(default='', max_length=700000)
    accent: str = Field(default='lime', pattern='^(lime|cyan|violet|coral)$')
    density: str = Field(default='comfortable', pattern='^(comfortable|compact)$')
    motionLevel: str = Field(default='soft', pattern='^(full|soft|off)$')
    homeWidgets: list[str] = Field(default_factory=lambda: ['progress', 'reports', 'overview', 'studio'], min_length=1, max_length=4)

@app.get('/api/profile')
def get_profile():
    with database() as db:
        row = db.execute("SELECT payload FROM settings WHERE key='profile'").fetchone()
    stored = json.loads(row[0]) if row else {}
    return {**ProfileInput().model_dump(), **stored}

@app.put('/api/profile')
def update_profile(profile: ProfileInput):
    profile.name = profile.name.strip()
    if not profile.name:
        raise HTTPException(422, 'Enter a name.')
    if any(widget not in {'progress', 'reports', 'overview', 'studio'} for widget in profile.homeWidgets):
        raise HTTPException(422, 'Choose from the available home dashboard widgets.')
    if len(set(profile.homeWidgets))!=len(profile.homeWidgets):raise HTTPException(422,'Choose each home shortcut only once.')
    if profile.avatar:
        import base64,binascii
        try:
            header,encoded=profile.avatar.split(',',1)
            if header not in ('data:image/jpeg;base64','data:image/png;base64','data:image/webp;base64'):raise ValueError()
            photo=base64.b64decode(encoded,validate=True)
            valid=photo.startswith(b'\xff\xd8\xff') if 'jpeg' in header else photo.startswith(b'\x89PNG\r\n\x1a\n') if 'png' in header else photo[:4]==b'RIFF' and photo[8:12]==b'WEBP'
            if not valid or len(photo)>500000:raise ValueError()
        except (ValueError,binascii.Error):raise HTTPException(422,'Use a JPG, PNG or WebP profile photo under 500 KB.')
    data = profile.model_dump()
    with database() as db:
        db.execute("INSERT OR REPLACE INTO settings VALUES ('profile', ?)", (json.dumps(data),))
    return data

@app.get('/healthz',include_in_schema=False)
def readiness():
    if not camera_assets()['ready']:raise HTTPException(503,'Camera assets are missing.')
    if os.getenv('MOTIONAI_REQUIRE_MODEL','1' if production() else '0')=='1' and model is None:raise HTTPException(503,'Analysis model is not ready.')
    return {'status':'ready'}

@app.get('/api/health')
def health():
    installation_id=hashlib.sha256(str(ROOT.resolve()).casefold().encode('utf-8')).hexdigest()[:16]
    return {'status':'healthy', 'app':'motionai', 'version':app.version, 'api_version':2, 'installation_id':installation_id, 'camera':camera_assets(), 'motionbert':{'loaded':model is not None, 'state':model_state, 'name':'MotionBERT-Lite / DSTformer', 'error':model_error, 'parameters':parameters, 'checkpoint_sha256':model_hash}}

def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and bool(np.isfinite(value))

def finite_json(value):
    if isinstance(value, float):
        return bool(np.isfinite(value))
    if isinstance(value, dict):
        return all(finite_json(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_json(item) for item in value)
    return value is None or isinstance(value, (str, int, bool))

def session_summary(data):
    return {key:value for key,value in data.items() if key not in ('frames','motionbert')} | {'frame_count':len(data['frames']), 'analyzed':bool(data.get('motionbert'))}

def validate_session(data):
    if not isinstance(data, dict) or data.get('exercise') not in EXERCISES:
        raise HTTPException(422, 'Select a supported exercise.')
    frames = data.get('frames')
    if not isinstance(frames, list) or not 2 <= len(frames) <= 3600:
        raise HTTPException(422, 'Recording must contain 2 to 3,600 frames.')
    previous = -1
    for frame in frames:
        if not isinstance(frame, dict):
            raise HTTPException(422, 'Invalid recording frame.')
        stamp = frame.get('timestamp')
        if not finite_number(stamp) or not 0 <= stamp <= 86_400_000 or stamp <= previous:
            raise HTTPException(422, 'Frame timestamps must be finite and strictly increasing.')
        previous = stamp
        for dimension in ('width','height'):
            value = frame.get(dimension)
            if not finite_number(value) or not 1 <= value <= 8192 or not float(value).is_integer():
                raise HTTPException(422, 'Each frame must include valid video width and height.')
        for name in ('image','world'):
            joints = frame.get(name)
            if not isinstance(joints,list) or len(joints) != 33:
                raise HTTPException(422, 'Expected 33 MediaPipe image and world landmarks per frame.')
            for point in joints:
                if not isinstance(point,dict) or not finite_json(point) or any(not finite_number(point.get(k)) for k in ('x','y','z')):
                    raise HTTPException(422, 'Joint coordinates must be finite numbers.')
                confidence = point.get('visibility',0)
                if not finite_number(confidence) or not 0 <= confidence <= 1:
                    raise HTTPException(422, 'Joint visibility must be between zero and one.')
        metrics = frame.get('metrics')
        if not isinstance(metrics,dict) or not finite_json(metrics) or not finite_number(metrics.get('primary')) or not 0 <= metrics['primary'] <= 180:
            raise HTTPException(422, 'Invalid measured angles.')
        for side in ('left', 'right'):
            value = metrics.get(side)
            if value is not None and (not finite_number(value) or not 0 <= value <= 180):
                raise HTTPException(422, 'Invalid measured angles.')
            reliable = metrics.get(side + 'Reliable')
            if reliable is not None and (not isinstance(reliable, bool) or reliable != (value is not None)):
                raise HTTPException(422, 'Joint reliability must match the available angle.')
        if metrics.get('left') is None and metrics.get('right') is None:
            raise HTTPException(422, 'Each recorded frame needs at least one measured side.')
        body_angle = metrics.get('bodyAngle')
        if body_angle is not None and (not finite_number(body_angle) or not 0 <= body_angle <= 180):
            raise HTTPException(422, 'Invalid body angle.')
        if not finite_json(frame):
            raise HTTPException(422, 'Recording contains invalid numeric values.')
    for key,lo,hi in [('reps',0,10000),('duration',0,86400),('target',1,100)]:
        value=data.get(key)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not np.isfinite(value) or not lo<=value<=hi or (key in ('reps','target') and not float(value).is_integer()):
            raise HTTPException(422, f'Invalid {key}.')
    if data.get('source') not in ('camera','import'):
        raise HTTPException(422, 'Recording source must be camera or import.')
    try:
        date = data.get('date')
        if not isinstance(date, str):
            raise ValueError()
        parsed=datetime.fromisoformat(date.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
    except (TypeError,ValueError):
        raise HTTPException(422, 'Invalid session date.')
    # Model outputs are server-owned, never trusted from an uploaded JSON file.
    clean = {key:data[key] for key in ('exercise','date','reps','duration','target','source','frames')}
    clean['date'] = parsed.astimezone(timezone.utc).isoformat()
    if frames[-1]['timestamp'] > (data['duration'] + 2) * 1000:
        raise HTTPException(422, 'Frame timestamps exceed the session duration.')
    clean['status'] = 'completed' if data['reps'] >= data['target'] else 'partial'
    return clean

@app.get('/api/sessions')
def list_sessions():
    with database() as db:
        rows=db.execute('SELECT payload FROM sessions ORDER BY date DESC').fetchall()
    return sorted([session_summary(json.loads(row[0])) for row in rows],key=lambda s:datetime.fromisoformat(s['date'].replace('Z','+00:00')),reverse=True)

@app.post('/api/sessions', status_code=201)
def create_session(data: dict):
    clean=validate_session(data)
    client_id=data.get('client_id')
    try:
        if client_id is not None and not isinstance(client_id,str):
            raise ValueError()
        clean['id']=str(uuid.UUID(client_id)) if client_id is not None else str(uuid.uuid4())
    except (ValueError,AttributeError):
        raise HTTPException(422, 'The recording recovery key must be a valid UUID.')
    clean['motionbert']=None
    with database() as db:
        inserted=db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?,?)',(clean['id'],clean['date'],json.dumps(clean,allow_nan=False)))
        if inserted.rowcount == 0:
            existing=json.loads(db.execute('SELECT payload FROM sessions WHERE id=?',(clean['id'],)).fetchone()[0])
            if any(existing.get(key) != clean[key] for key in ('exercise','date','reps','duration','target','source','frames')):
                raise HTTPException(409, 'This recovery key belongs to a different recording. Your existing recording has been kept.')
            return existing
    return clean

def read_session(session_id):
    with database() as db:
        row=db.execute('SELECT payload FROM sessions WHERE id=?',(session_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Session not found.')
    return json.loads(row[0])

@app.get('/api/sessions/{session_id}')
def get_session(session_id: str):
    return read_session(session_id)

@app.delete('/api/sessions/{session_id}')
def delete_session(session_id: str):
    with lock:
        read_session(session_id)
        with database() as db:
            db.execute('DELETE FROM sessions WHERE id=?',(session_id,))
    return {'deleted':True}

def mediapipe_to_h36m(frames):
    data=[]
    for frame in frames:
        p=np.array([[joint['x'],joint['y'],joint.get('visibility',0)] for joint in frame['image']],dtype=np.float32)
        hip=(p[23]+p[24])/2
        neck=(p[11]+p[12])/2
        head=p[0].copy()
        head[:2] += (p[0,:2]-neck[:2])*0.5
        head[2]=min(p[0,2],neck[2])*0.75
        joints=np.stack([hip,p[24],p[26],p[28],p[23],p[25],p[27],(hip+neck)/2,neck,p[0],head,p[11],p[13],p[15],p[12],p[14],p[16]])
        w,h=frame['width'],frame['height']
        # Match the official in-the-wild input convention: image-center origin,
        # divide pixel x/y by half the smaller image dimension; confidence unchanged.
        joints[:,:2]=(joints[:,:2]*np.array([w,h])-np.array([w,h])/2)/(min(w,h)/2)
        data.append(joints)
    return np.stack(data).astype(np.float32)

def joint_angle(a,b,c):
    u,v=a-b,c-b
    norm=np.linalg.norm(u,axis=-1)*np.linalg.norm(v,axis=-1)
    dot=np.sum(u*v,axis=-1)/np.maximum(norm,1e-8)
    return np.degrees(np.arccos(np.clip(dot,-1,1)))

def motion_analysis(session):
    import torch
    tensor=mediapipe_to_h36m(session['frames'])
    output=[]
    started=time.perf_counter()
    with torch.inference_mode():
        # Do not infer temporal continuity across camera/visibility gaps.
        boundaries=[0]+[i for i in range(1,len(tensor)) if session['frames'][i]['timestamp']-session['frames'][i-1]['timestamp']>650]+[len(tensor)]
        for begin,end in zip(boundaries,boundaries[1:]):
            for offset in range(begin,end,243):
                clip=torch.from_numpy(tensor[offset:min(offset+243,end)]).unsqueeze(0)
                prediction=model(clip).squeeze(0).cpu().numpy()
                output.append(prediction)
    pose=np.concatenate(output)
    if not np.isfinite(pose).all():
        raise RuntimeError('Model produced invalid coordinates.')
    pose=pose-pose[:,0:1,:]
    exercise=session['exercise']
    if exercise in ('push_up','shoulder_press'):
        left=joint_angle(pose[:,11],pose[:,12],pose[:,13]);right=joint_angle(pose[:,14],pose[:,15],pose[:,16])
    elif exercise=='jumping_jack':
        left=joint_angle(pose[:,4],pose[:,11],pose[:,12]);right=joint_angle(pose[:,1],pose[:,14],pose[:,15])
    else:
        left=joint_angle(pose[:,4],pose[:,5],pose[:,6]);right=joint_angle(pose[:,1],pose[:,2],pose[:,3])
    # Model convention: y points down. Viewer convention: y up, z reversed.
    viewer=pose.copy();viewer[:,:,1:]*=-1
    return {'status':'complete','model':'MotionBERT-Lite · H36M fine-tuned 3D pose','checkpoint_sha256':model_hash,'parameters':parameters,'latency_ms':round((time.perf_counter()-started)*1000,2),'input_shape':[1,min(243,len(tensor)),17,3],'windows':len(output),'frames':viewer.round(6).tolist(),'trajectories':{'left':left.round(2).tolist(),'right':right.round(2).tolist()},'stats':{'left_min':round(float(left.min()),2),'left_max':round(float(left.max()),2),'right_min':round(float(right.min()),2),'right_max':round(float(right.max()),2),'left_rom':round(float(np.ptp(left)),2),'right_rom':round(float(np.ptp(right)),2),'mean_difference':round(float(np.abs(left-right).mean()),2)},'mapping_notes':['Pelvis and neck are hip/shoulder midpoints. Spine is their midpoint.','Head is a virtual point extrapolated from nose and neck, with reduced confidence.','Input channels are normalized image x/y and visibility, not world x/y/z.','Predictions use monocular camera estimates; no metric scale or clinical accuracy is claimed.','Up to 243 consecutive frames per model window. Tracking gaps retain their timestamps.','Exercise selection and rep counting use camera rules; this checkpoint performs 3D pose lifting, not exercise classification.']}

@app.post('/api/sessions/{session_id}/analyze')
def analyze_session(session_id: str):
    if model is None:
        raise HTTPException(503, 'MotionBERT is unavailable. Live recording still works; ask the owner to check model readiness.')
    with analysis_slot():
        data=read_session(session_id)
        if data.get('motionbert'):
            return data
        try:
            data['motionbert']=motion_analysis(data)
        except Exception as exc:
            logger.exception('MotionBERT inference failed')
            raise HTTPException(500, 'Analysis could not finish. Your recording is saved; please retry.') from exc
        with database() as db:
            db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(data,allow_nan=False),session_id))
    return data

@app.get('/api/dataset')
def research_catalog():
    from backend.dataset import catalog
    return catalog()

@app.get('/api/dataset/{name}')
def research_recording(name:str):
    from backend.dataset import recording
    try:return recording(name)[0]
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc))

@app.post('/api/dataset/{name}/analyze')
def research_analysis(name:str):
    import torch
    from backend.dataset import model_input
    if model is None:raise HTTPException(503,'MotionBERT is unavailable')
    try:data,tensor=model_input(name)
    except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc))
    if len(tensor)>3600:raise HTTPException(422,'Recording exceeds model frame limit')
    with analysis_slot(),torch.inference_mode():
        result=[model(torch.from_numpy(tensor[i:i+243]).unsqueeze(0)).squeeze(0).cpu().numpy() for i in range(0,len(tensor),243)]
    pose=np.concatenate(result);pose-=pose[:,0:1];pose[:,:,1:]*=-1
    if not np.isfinite(pose).all():raise HTTPException(500,'Model produced invalid coordinates')
    return {'frames':pose.round(6).tolist(),'timestamps':data['timestamps'],'windows':len(result),'model':'MotionBERT-Lite','note':'Kinect depth-image joints mapped to H36M; virtual nose from neck/head. Body-box normalization. Cross-sensor domain shift: predictions are exploratory and do not establish correctness.'}

from backend.routines import register_routines
register_routines(app, database)
from backend.reports import register_reports
register_reports(app, database, read_session, validate_session, session_summary)
from backend.assistant import register_assistant
register_assistant(app, list_sessions, read_session)

@app.get('/{path:path}', include_in_schema=False)
def frontend(path: str):
    base=(ROOT/'dist').resolve()
    candidate=(base/path).resolve()
    if candidate.is_relative_to(base) and candidate.is_file():
        mime = {'.wasm':'application/wasm', '.task':'application/octet-stream', '.js':'application/javascript', '.css':'text/css'}.get(candidate.suffix)
        return FileResponse(candidate, media_type=mime, headers={'Cache-Control':'no-cache'})
    if path == 'api' or path.startswith('api/'):
        raise HTTPException(404, 'Endpoint not found.')
    # A missing JS, WASM or model file must never masquerade as a successful HTML response.
    if not candidate.is_relative_to(base) or candidate.suffix or path.startswith(('assets/', 'mediapipe/')):
        raise HTTPException(404, 'Application asset not found. Rebuild or restore the complete application folder.')
    index=base/'index.html'
    if not index.is_file():
        raise HTTPException(503, 'Build the frontend first with npm run build.')
    return FileResponse(index, headers={'Cache-Control':'no-cache'})
