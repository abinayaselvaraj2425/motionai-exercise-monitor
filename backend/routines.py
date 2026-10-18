"""Persistent routine orchestration; camera recordings remain normal MotionBERT sessions."""
import json
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException

def guide(key, name, cue, seconds=30):
    return dict(key=key, name=name, cue=cue, seconds=seconds)

def movement(exercise, name, reps):
    return dict(key=exercise, name=name, exercise=exercise, target=reps)

WARM = guide('upper', 'Head & shoulder warm-up', 'Stand comfortably. Gently turn your head left and right, then roll your shoulders slowly. Stay within a comfortable range.')
COOL = guide('cool', 'Ankles & breathing', 'Seated or holding a stable support, gently circle each ankle. Finish with relaxed breathing.', 45)
TEMPLATES = [
    dict(id='morning', name='Morning routine', tag='YOUR DAILY RESET', description='A guided head-to-toe session: neck and shoulders, upper body, legs, whole-body movement and ankles.', steps=[WARM, movement('shoulder_press','Shoulder press · no weights',8), movement('squat','Bodyweight squat',10), movement('lunge','Forward lunge · alternate legs',8), movement('jumping_jack','Jumping jack',12), COOL]),
    dict(id='full-body', name='Full-body circuit', tag='MOVE EVERY REGION', description='A longer circuit with upper-body, lower-body and whole-body exercises. Set up your camera for each movement.', steps=[WARM, movement('shoulder_press','Shoulder press · no weights',10), movement('push_up','Push-up',6), movement('squat','Bodyweight squat',12), movement('lunge','Forward lunge · alternate legs',10), movement('jumping_jack','Jumping jack',15), COOL]),
    dict(id='standing', name='Standing reset', tag='A SHORTER SESSION', description='A compact standing sequence with no floor exercise or jumping.', steps=[WARM, movement('shoulder_press','Shoulder press · no weights',8), movement('squat','Bodyweight squat',8), COOL]),
]

def register_routines(app, database):
    def table(db):
        db.execute('CREATE TABLE IF NOT EXISTS routines (id TEXT PRIMARY KEY, date TEXT NOT NULL, payload TEXT NOT NULL)')

    def reconcile(db, run):
        # A save that succeeded just before a browser reload is picked up automatically.
        for step in run['steps']:
            if 'exercise' not in step:
                continue
            row = db.execute('SELECT payload FROM sessions WHERE id=?', (step['recording_id'],)).fetchone()
            if row:
                s = json.loads(row[0])
                if s['exercise'] == step['exercise'] and s['source'] == 'camera':
                    step.update(status='done' if s['reps'] >= step['target'] else 'partial', session_id=s['id'], reps=s['reps'], duration=s['duration'])
            elif step.get('session_id'):
                step.update(status='missing', reps=0, duration=0)
        run['reps'] = sum(s.get('reps', 0) for s in run['steps'])
        run['duration'] = sum(s.get('duration', 0) for s in run['steps'])
        run['complete'] = all(s['status'] == 'done' for s in run['steps'])
        return run

    @app.get('/api/routine-templates')
    def templates():
        return TEMPLATES

    @app.get('/api/routines')
    def runs():
        with database() as db:
            table(db)
            return [reconcile(db, json.loads(row[0])) for row in db.execute('SELECT payload FROM routines ORDER BY date DESC').fetchall()]

    @app.post('/api/routines', status_code=201)
    def start(data: dict):
        template = next((t for t in TEMPLATES if t['id'] == data.get('template')), None)
        if not template:
            raise HTTPException(422, 'Select an available routine.')
        try:
            run_id = str(uuid.UUID(data.get('id', '')))
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(422, 'Invalid routine key.')
        with database() as db:
            table(db)
            existing = db.execute('SELECT payload FROM routines WHERE id=?', (run_id,)).fetchone()
            if existing:
                run = json.loads(existing[0])
                if run['template'] != template['id']:
                    raise HTTPException(409, 'This key already belongs to another routine.')
                return reconcile(db, run)
            now = datetime.now(timezone.utc).isoformat()
            run = dict(id=run_id, template=template['id'], name=template['name'], date=now, ended=None, steps=[dict(s, status='pending', recording_id=str(uuid.uuid4())) for s in template['steps']])
            db.execute('INSERT INTO routines VALUES (?,?,?)', (run_id, now, json.dumps(run)))
            return reconcile(db, run)

    @app.patch('/api/routines/{run_id}')
    def update(run_id: str, data: dict):
        with database() as db:
            table(db)
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM routines WHERE id=?', (run_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Routine not found.')
            run = reconcile(db, json.loads(row[0]))
            if run['ended']:
                return run
            if data.get('finish') is True:
                for step in run['steps']:
                    if step['status'] == 'pending':
                        step['status'] = 'skipped'
                run['ended'] = datetime.now(timezone.utc).isoformat()
            else:
                index = data.get('step')
                if type(index) is not int or not 0 <= index < len(run['steps']):
                    raise HTTPException(422, 'Invalid routine step.')
                step = run['steps'][index]
                if any(s['status'] == 'pending' for s in run['steps'][:index]):
                    raise HTTPException(409, 'Finish or skip the earlier steps first.')
                status = data.get('status')
                if status not in ('done', 'skipped') or (status == 'done' and 'exercise' in step):
                    raise HTTPException(422, 'Tracked steps require a saved camera recording.')
                if step['status'] == 'pending':
                    step['status'] = status
                    step['duration'] = step.get('seconds', 0) if status == 'done' else 0
            run = reconcile(db, run)
            db.execute('UPDATE routines SET payload=? WHERE id=?', (json.dumps(run), run_id))
            return run
