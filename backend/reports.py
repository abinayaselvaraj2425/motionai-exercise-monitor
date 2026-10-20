"""Versioned movement observations, account-scoped backup and tabular export.

These are engineering heuristics, not clinical thresholds or a correctness classifier.
Angles are recomputed from coordinates; imported metrics and analysis are not trusted.
"""
import csv
import io
import json
import hashlib
import uuid
from datetime import datetime
import numpy as np
from fastapi import HTTPException
from fastapi.responses import Response

METHOD = 'movement-observations-v2'
NAMES={'squat':'Bodyweight squat','lunge':'Forward lunge','push_up':'Push-up','jumping_jack':'Jumping jack','shoulder_press':'Shoulder press'}
JOINTS={'squat':[(23,25,27),(24,26,28)],'lunge':[(23,25,27),(24,26,28)],'push_up':[(11,13,15),(12,14,16)],'shoulder_press':[(11,13,15),(12,14,16)],'jumping_jack':[(23,11,13),(24,12,14)]}
H36={'squat':[(4,5,6),(1,2,3)],'lunge':[(4,5,6),(1,2,3)],'push_up':[(11,12,13),(14,15,16)],'shoulder_press':[(11,12,13),(14,15,16)],'jumping_jack':[(4,11,12),(1,14,15)]}
FOCUS={'squat':'Lower and rise at a steady pace, with your feet grounded.','lunge':'Use a clear split stance and return to your starting position between repetitions.','push_up':'Move your shoulders and hips together as you lower and press up.','shoulder_press':'Press overhead with control and keep your wrists above your elbows.','jumping_jack':'Coordinate opening your arms and feet, then return to your starting position.'}

def frame_gate(ex,image,world,width,height):
    """Exercise-position evidence, independently recomputed from the recording."""
    def visible(ids):return all(image[j].get('visibility',0)>=.45 and -.025<=image[j]['x']<=1.025 and -.025<=image[j]['y']<=1.025 for j in ids)
    positions=[];gestures=[]
    for o in (0,1):
        required=[11+o,23+o]+([13+o,15+o,27+o] if ex=='push_up' else [13+o,15+o] if ex in ('shoulder_press','jumping_jack') else [25+o,27+o])
        if not visible(required):positions.append(False);gestures.append(False);continue
        shoulder,hip=image[11+o],image[23+o]
        if ex=='push_up':
            dx=abs(shoulder['x']-hip['x']);dy=abs(shoulder['y']-hip['y']);body=angle(world,(11+o,23+o,27+o))
            positioned=dx>=.06 and dy<=dx*1.15 and body is not None and body>=135
        else:positioned=shoulder['y']<hip['y']-.025
        gesture=True
        if ex=='shoulder_press':
            elevation=angle(world,(23+o,11+o,13+o))
            gesture=image[15+o]['y']<shoulder['y']-.015 and elevation is not None and elevation>80
        positions.append(positioned);gestures.append(gesture)
    positioned=any(positions);gesture=any(p and g for p,g in zip(positions,gestures))
    if ex=='jumping_jack':
        positioned=all(positions) and visible([27,28])
        scale=max(.04,abs(image[23]['x']-image[24]['x']),abs(image[11]['x']-image[12]['x'])*.75)
        gesture=positioned and abs(image[27]['x']-image[28]['x'])>=scale*1.8 and all(image[15+o]['y']<image[11+o]['y']-.015 for o in (0,1))
    elif ex=='lunge' and visible([27,28]):
        feet=np.linalg.norm(np.asarray(world[27])[[0,2]]-np.asarray(world[28])[[0,2]])
        leg=max(np.linalg.norm(np.asarray(world[23])-np.asarray(world[27])),np.linalg.norm(np.asarray(world[24])-np.asarray(world[28])))
        gesture=positioned and feet>leg*.3
    return positioned,gesture

def angle(points, ids):
    a,b,c=[np.asarray(points[i],dtype=float) for i in ids]
    u,v=a-b,c-b
    d=np.linalg.norm(u)*np.linalg.norm(v)
    return None if d<1e-8 else float(np.degrees(np.arccos(np.clip(np.dot(u,v)/d,-1,1))))

def number(v): return round(float(v),1) if v is not None and np.isfinite(v) else None
def median(v): return number(np.median(v)) if len(v) else None

def report(session):
    ex=session['exercise'];frames=session['frames'];model=session.get('motionbert')
    use_model=bool(model and len(model.get('frames',[]))==len(frames))
    sides=[[],[]];body=[];slants=[];primary=[];times=[];gestures=[];excluded=0
    for i,f in enumerate(frames):
        world=[[j['x'],j['y'],j['z']] for j in f['world']]
        points=model['frames'][i] if use_model else world
        image=f['image'];both=[]
        for k,ids in enumerate(JOINTS[ex]):
            reliable=all(image[j].get('visibility',0)>=.45 and -.025<=image[j]['x']<=1.025 and -.025<=image[j]['y']<=1.025 for j in ids)
            value=angle(points,(H36 if use_model else JOINTS)[ex][k]) if reliable else None
            sides[k].append(value)
            both.append(value)
        positioned,gesture=frame_gate(ex,image,world,f['width'],f['height'])
        values=[v for v in both if v is not None]
        primary.append((min(values) if values and ex in ('lunge','jumping_jack') else median(values)) if positioned else None)
        gestures.append(gesture)
        if not positioned:excluded+=1
        times.append(f['timestamp']/1000)
        if all(image[j].get('visibility',0)>=.45 for j in (11,23,27)):
            body.append(angle(points,(11,4,6) if use_model else (11,23,27)))
        if ex=='shoulder_press' and all(image[j].get('visibility',0)>=.45 for j in (13,15)):
            dx=(image[15]['x']-image[13]['x'])*f['width'];dy=(image[15]['y']-image[13]['y'])*f['height']
            slants.append(float(np.degrees(np.arctan2(abs(dx),max(.001,abs(dy))))))
    valid=[v for v in primary if v is not None]
    valid_seconds=sum(min(.2,max(0,times[i]-times[i-1])) for i in range(1,len(times)) if primary[i] is not None and primary[i-1] is not None)
    coverage=min(100,round(100*valid_seconds/max(1,session['duration'])))
    # Detect measurable excursions; keep these separate from the live rep count.
    cycles=[];state='wait';baseline=extreme=None;start=0;last=None
    extension=ex in ('shoulder_press','jumping_jack')
    for i,(t,v) in enumerate(zip(times,primary)):
        if v is None or last is not None and t-last>.65:
            state='wait';baseline=None
        last=t
        if v is None: continue
        rest=v<=(50 if ex=='jumping_jack' else 130) if extension else v>=135
        if state=='wait':
            if rest: state='ready';baseline=extreme=v;start=i
            continue
        if state=='ready' and rest:
            baseline=min(baseline,v) if extension else max(baseline,v)
        excursion=(v-baseline) if extension else (baseline-v)
        extreme=max(extreme,v) if extension else min(extreme,v)
        if state=='ready':
            if abs(v-baseline)<10: start=i
            if excursion>= (65 if ex=='jumping_jack' else 25) and gestures[i]: state='out'
        elif state=='out' and (v<=baseline+14 if extension else v>=baseline-14):
            duration=t-times[start]
            if .6<=duration<=30:
                segment=primary[start:i+1]
                cycles.append({'range':number(abs(extreme-baseline)),'duration':number(duration),'peak':number(extreme),'start':start,'end':i})
            state='ready';baseline=extreme=v;start=i
        if t-times[start]>30: state='wait'
    usable=len(valid)>=10 and valid_seconds>=1
    ranges=[c['range'] for c in cycles];durations=[c['duration'] for c in cycles]
    paired=[abs(a-b) for a,b in zip(*sides) if a is not None and b is not None]
    typical=median(ranges) if usable and len(cycles)>=2 else None
    variation=median([abs(x-typical) for x in ranges]) if typical is not None else None
    source='MotionBERT 3D' if use_model else 'Camera 3D estimate'
    metrics=[dict(key='range',label='Typical movement range',value=typical,unit='°',description='Median joint excursion across measurable cycles. A larger range is not automatically better.'),dict(key='tempo',label='Typical repetition time',value=median(durations) if len(cycles)>=2 else None,unit='s',description='Median elapsed time of measurable cycles; tracking gaps are excluded.'),dict(key='variation',label='Range variation',value=variation,unit='°',description='Median absolute difference from your typical range. Smaller values mean more consistent range.'),dict(key='difference',label='Left–right angle difference',value=median(paired) if usable and len(paired)>=10 and ex!='lunge' else None,unit='°',description='Median simultaneous angle difference. Camera perspective can affect this; alternating lunges are not compared this way.')]
    observations=[];focus=FOCUS[ex]
    if not usable: observations.append('There is not enough reliable tracking to describe your movement. Your saved repetition count is kept.')
    elif len(cycles)<2: observations.append('Too few complete measurable cycles for a reliable range or timing summary.')
    else:
        observations.append(f'We measured {len(cycles)} movement cycles, with a typical range of {typical}°.')
        if variation is not None: observations.append(f'Your range typically varied by {variation}° between cycles. This describes consistency, not exercise correctness.')
        if len(cycles)>=6:
            early=np.median(ranges[:3]);late=np.median(ranges[-3:]);delta=number(late-early)
            observations.append(f'Your last three measurable cycles had {abs(delta)}° {"more" if delta>=0 else "less"} range than your first three. The cause cannot be determined from movement alone.')
    if ex=='push_up' and len(body)>=10 and np.median(body)<155:
        observations.append('The shoulder–hip–ankle estimate frequently departed from a straight line. Check the side-view replay.');focus='Try moving your shoulders and hips together, keeping a comfortable plank position.'
    if ex=='shoulder_press' and len(slants)>=10 and np.median(slants)>30:
        observations.append('The camera view suggests your forearms were often angled away from vertical. Perspective can affect this observation.');focus='Check that your wrists stay approximately above your elbows as you press.'
    return dict(version=METHOD,source=source,exercise=ex,coverage=coverage,measured_cycles=len(cycles),metrics=metrics,observations=observations,focus=focus,cycles=cycles,trajectories={'left':sides[0],'right':sides[1],'times':[f['timestamp'] for f in frames]},method={'joint':'Shoulder elevation' if ex=='jumping_jack' else 'Elbow bend' if ex in ('push_up','shoulder_press') else 'Knee bend','convention':'Geometric angle: 180° is a straight knee or elbow. Range is excursion, not maximum flexion.','quality':'Only visible joints are measured. Coverage estimates tracked seconds divided by active recording time. It is not a probability of accuracy.','limits':'Heuristic movement observations, not a diagnosis, strength measurement or medical recovery score. Use the same camera view and exercise variation when comparing.'})

def register_reports(app,database,read_session,validate_session,session_summary):
    def all_data():
        with database() as db:
            db.execute('CREATE TABLE IF NOT EXISTS routines (id TEXT PRIMARY KEY,date TEXT NOT NULL,payload TEXT NOT NULL)')
            sessions=[json.loads(r[0]) for r in db.execute('SELECT payload FROM sessions ORDER BY date DESC')]
            from backend.routines import reconcile
            routines=[reconcile(db,json.loads(r[0])) for r in db.execute('SELECT payload FROM routines ORDER BY date DESC')]
        return sessions,routines

    @app.get('/api/sessions/{session_id}/report')
    def get_report(session_id:str):
        session=read_session(session_id);result=report(session)
        sessions,_=all_data();previous=[]
        current_metrics={m['key']:m['value'] for m in result['metrics']}
        stamp=lambda s:datetime.fromisoformat(s['date'].replace('Z','+00:00'))
        for older in sorted(sessions,key=stamp,reverse=True):
            if older['exercise']!=session['exercise'] or stamp(older)>=stamp(session) or bool(older.get('motionbert'))!=bool(session.get('motionbert')): continue
            r=report(older)
            if r['coverage']>=60 and r['measured_cycles']>=2:
                previous.append({'id':older['id'],'date':older['date'],'metrics':r['metrics']})
            if len(previous)==2: break
        changes=[]
        if result['coverage']>=60 and result['measured_cycles']>=2 and len(previous)==2:
            for key in ('range','tempo','variation'):
                values=[next(m['value'] for m in p['metrics'] if m['key']==key) for p in previous]
                if current_metrics[key] is not None and all(v is not None for v in values): changes.append({'key':key,'delta':number(current_metrics[key]-np.mean(values))})
        result['comparison']={'previous':previous,'changes':changes,'note':'Same exercise and analysis source; confirm the camera view, assistance and exercise variation were also similar. Numerical changes may include measurement error.' if changes else 'Two earlier sessions with the same exercise and analysis source, sufficient coverage and measurable cycles are needed.'}
        return result

    def selection(start,end,session_id,routine_id):
        sessions,routines=all_data()
        if session_id: sessions=[s for s in sessions if s['id']==session_id];routines=[]
        elif routine_id:
            routines=[r for r in routines if r['id']==routine_id]
            ids={s['recording_id'] for r in routines for s in r['steps']}
            sessions=[s for s in sessions if s['id'] in ids]
        elif start or end:
            try:
                lo=datetime.fromisoformat(start.replace('Z','+00:00')) if start else None
                hi=datetime.fromisoformat(end.replace('Z','+00:00')) if end else None
                if any(x is not None and x.tzinfo is None for x in (lo,hi)) or lo and hi and lo>=hi: raise ValueError()
            except ValueError: raise HTTPException(422,'Choose a valid date range.')
            inside=lambda x:(lo is None or datetime.fromisoformat(x['date'].replace('Z','+00:00'))>=lo) and (hi is None or datetime.fromisoformat(x['date'].replace('Z','+00:00'))<hi)
            sessions=[s for s in sessions if inside(s)]
            selected={s['id'] for s in sessions}
            routines=[r for r in routines if inside(r) or any(s['recording_id'] in selected for s in r['steps'])]
            # Keep entire selected routines so backups retain all their relationships.
            ids={s['recording_id'] for r in routines for s in r['steps']}
            full,_=all_data();sessions=[s for s in full if s['id'] in selected or s['id'] in ids]
        return sessions,routines

    @app.get('/api/export')
    def export(format:str='json',start:str='',end:str='',session_id:str='',routine_id:str=''):
        sessions,routines=selection(start,end,session_id,routine_id)
        if format=='json':
            backup={'format':'motionai-backup','version':2,'sessions':[{**s,'motionbert':None} for s in sessions],'routines':routines}
            if len(sessions)>100 or len(routines)>100 or len(json.dumps(backup,allow_nan=False).encode('utf-8'))>29_000_000:
                raise HTTPException(422,'This recording backup is too large to restore in one import. Export a shorter period or individual session. CSV summaries can still cover the full period.')
            return backup
        if format!='csv': raise HTTPException(422,'Choose CSV or JSON.')
        out=io.StringIO();writer=csv.writer(out)
        writer.writerow(['record_type','session_id','routine_id','date','exercise_or_step','status','reps','target','active_seconds','analysis_source','coverage_percent','measured_cycles','range_degrees','repetition_seconds','range_variation_degrees','side_difference_degrees','observations','next_focus','method_version'])
        links={st['recording_id']:r['id'] for r in routines for st in r['steps']}
        safe=lambda v: "'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@','\t','\r') else v
        for s in sessions:
            r=report(s);vals=[m['value'] for m in r['metrics']]
            writer.writerow([safe(v) for v in ['exercise',s['id'],links.get(s['id'],''),s['date'],NAMES[s['exercise']],s.get('status','completed' if s['reps']>=s['target'] else 'partial'),s['reps'],s['target'],s['duration'],r['source'],r['coverage'],r['measured_cycles'],*vals,' '.join(r['observations']),r['focus'],METHOD]])
        for r in routines:
            for st in r['steps']:
                if 'exercise' not in st or st.get('status') in ('skipped','missing','pending'):
                    writer.writerow([safe(v) for v in ['routine_step','',r['id'],r['date'],st['name'],st['status'],st.get('reps',''),st.get('target',''),st.get('duration',0),'Self-reported guided step' if 'exercise' not in st else 'Not recorded','','','','','','','','',METHOD]])
        return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="motionai-report.csv"'})

    @app.get('/api/trends')
    def trends(exercise:str,metric:str='range',source:str='camera',start:str='',end:str=''):
        if exercise not in NAMES or metric not in ('range','variation','tempo') or source not in ('camera','motionbert'):
            raise HTTPException(422,'Select a supported exercise, metric and source.')
        sessions,_=selection(start,end,'','')
        result=[]
        for s in sorted(sessions,key=lambda s:datetime.fromisoformat(s['date'].replace('Z','+00:00'))):
            if s['exercise']!=exercise or bool(s.get('motionbert'))!=(source=='motionbert'): continue
            r=report(s)
            result.append({'id':s['id'],'date':s['date'],'source':r['source'],'value':next(m['value'] for m in r['metrics'] if m['key']==metric) if r['coverage']>=60 else None})
        return result

    def prepare(data):
        if data.get('format')=='motionai-backup':
            if data.get('version')!=2: raise HTTPException(422,'Unsupported backup version.')
            incoming=data.get('sessions');runs=data.get('routines',[])
        else: incoming=[data];runs=[]
        if not isinstance(incoming,list) or len(incoming)>100 or not isinstance(runs,list) or len(runs)>100: raise HTTPException(422,'Import at most 100 sessions and routines at once.')
        clean=[];mapping={}
        existing,existing_runs=all_data()
        def fingerprint(s):
            from datetime import timezone
            canonical={k:s[k] for k in ('exercise','date','frames')}
            canonical['date']=datetime.fromisoformat(s['date'].replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
            return hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
        known={fingerprint(s):s['id'] for s in existing}
        duplicates=0
        for s in incoming:
            if not isinstance(s,dict): raise HTTPException(422,'Invalid session.')
            value=validate_session(s);fp=fingerprint(value)
            original=s.get('id')
            if not isinstance(original,(str,type(None))): raise HTTPException(422,'Invalid recording ID.')
            if fp in known: duplicates+=1;new_id=known[fp]
            else:
                new_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'motionai:'+fp));value.update(id=new_id,source='import',motionbert=None);clean.append(value);known[fp]=new_id
            if original:
                if original in mapping and mapping[original]!=new_id: raise HTTPException(422,'Two different recordings use the same ID. Import them separately.')
                mapping[original]=new_id
        prepared=[]
        for r in runs:
            if not isinstance(r,dict) or not isinstance(r.get('steps'),list) or len(r['steps'])>30: raise HTTPException(422,'Invalid routine.')
            # Import templates and step metadata only from the application's known templates.
            from backend.routines import TEMPLATES
            template=next((t for t in TEMPLATES if t['id']==r.get('template')),None)
            if not template or len(template['steps'])!=len(r['steps']): raise HTTPException(422,'Routine template is not supported.')
            try:
                if datetime.fromisoformat(r['date'].replace('Z','+00:00')).tzinfo is None: raise ValueError()
                if r.get('ended') and datetime.fromisoformat(r['ended'].replace('Z','+00:00')).tzinfo is None: raise ValueError()
            except (KeyError,TypeError,ValueError,AttributeError): raise HTTPException(422,'Invalid routine date.')
            run_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'motionai-routine:'+str(r.get('id'))+r['date']))
            if any(x['id']==run_id for x in existing_runs): continue
            steps=[]
            for t,st in zip(template['steps'],r['steps']):
                if not isinstance(st,dict) or st.get('key')!=t['key']: raise HTTPException(422,'Routine steps do not match the template.')
                sid=mapping.get(st.get('recording_id'))
                status=st.get('status')
                if status not in ('pending','done','partial','skipped','missing'): raise HTTPException(422,'Invalid step status.')
                if t.get('exercise') and not sid and status in ('done','partial'): status='missing'
                step=dict(t,status=status,recording_id=sid or str(uuid.uuid4()))
                if sid:
                    s=next((s for s in clean+existing if s['id']==sid),None)
                    if not s or s['exercise']!=t.get('exercise'): raise HTTPException(422,'Routine recording belongs to another exercise.')
                    step.update(session_id=sid,reps=s['reps'],duration=s['duration'],status='done' if s['reps']>=t['target'] else 'partial')
                elif 'exercise' not in t: step['duration']=t.get('seconds',0) if status=='done' else 0
                steps.append(step)
            prepared.append(dict(id=run_id,template=template['id'],name=template['name'],date=r['date'],ended=r.get('ended'),steps=steps,reps=sum(s.get('reps',0) for s in steps),duration=sum(s.get('duration',0) for s in steps),complete=all(s['status']=='done' for s in steps)))
        return clean,prepared,duplicates

    @app.post('/api/import/preview')
    def preview(data:dict):
        sessions,routines,duplicates=prepare(data)
        return {'sessions':len(sessions),'routines':len(routines),'duplicates':duplicates,'note':'Existing recordings are kept. Imported model outputs are discarded and can be recomputed.'}

    @app.post('/api/import')
    def import_data(data:dict):
        sessions,routines,duplicates=prepare(data)
        with database() as db:
            for s in sessions: db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?,?)',(s['id'],s['date'],json.dumps(s,allow_nan=False)))
            for r in routines: db.execute('INSERT OR IGNORE INTO routines VALUES (?,?,?)',(r['id'],r['date'],json.dumps(r,allow_nan=False)))
        return {'sessions':len(sessions),'routines':len(routines),'duplicates':duplicates}
