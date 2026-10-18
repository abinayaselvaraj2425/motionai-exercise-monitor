import React, {useEffect, useRef, useState} from 'react';
import {Camera, CameraOff, Pause, Play, ScanLine, Check, AlertCircle, FlipHorizontal2, Layers, Volume2, VolumeX, LoaderCircle, Download, RefreshCw, X} from 'lucide-react';
import {exercises, ExerciseType, Joint, PoseTracker, PoseMeasurement, RepCounter, movementTargets} from '../pose';
import {api, RecordedFrame, WorkoutSession, formatTime, saveFile} from '../data';
import {PoseClient} from '../PoseClient';
import {cameraError, errorText, openCamera, playCamera, stopStream} from '../camera';
import {readDraft, writeDraft, SessionDraft} from '../draft';
import {MovementDemo} from './MovementDemo';
const edges=[[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28],[27,29],[29,31],[28,30],[30,32]];
function draw(canvas:HTMLCanvasElement,image:Joint[],width:number,height:number){
 if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
 const ctx=canvas.getContext('2d');if(!ctx)return;ctx.clearRect(0,0,width,height);
 const visible=(i:number)=>image[i]&&Number.isFinite(image[i].x+image[i].y)&&(image[i].visibility??0)>=.45;
 ctx.lineWidth=Math.max(2,width/300);ctx.lineCap='round';
 for(const [a,b] of edges)if(visible(a)&&visible(b)){ctx.strokeStyle=a%2?'#8ef0cf':'#c3b3ff';ctx.beginPath();ctx.moveTo(image[a].x*width,image[a].y*height);ctx.lineTo(image[b].x*width,image[b].y*height);ctx.stroke();}
 image.forEach((p,i)=>{if(i<11||!visible(i))return;ctx.beginPath();ctx.arc(p.x*width,p.y*height,Math.max(3,width/200),0,Math.PI*2);ctx.fillStyle='#f3fff9';ctx.fill();});
}
type Stage='idle'|'requesting'|'loading'|'tracking'|'paused'|'saving'|'recovery'|'checking';
interface Props{autoStart?:boolean;autoFinishAtTarget?:boolean;recordingId?:string;lockExercise?:boolean;initialExercise:ExerciseType;target:number;audio:boolean;onSaved:(session:WorkoutSession)=>void;onActiveChange:(active:boolean)=>void;}
export const LiveCameraTracker:React.FC<Props>=({initialExercise,target,audio,onSaved,onActiveChange,recordingId,lockExercise,autoStart=false,autoFinishAtTarget=false})=>{
 const autoStartAttempted=useRef(false);
 const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null),sampleCanvas=useRef<HTMLCanvasElement>(null);
 const stream=useRef<MediaStream|null>(null),detector=useRef<PoseClient|null>(null),abort=useRef<AbortController|null>(null),generation=useRef(0),raf=useRef(0),mounted=useRef(false),operation=useRef(false),running=useRef(false),pausedRef=useRef(false),pauseEpoch=useRef(0);
 const tracker=useRef(new PoseTracker()),counter=useRef(new RepCounter()),records=useRef<RecordedFrame[]>([]),draft=useRef<SessionDraft|null>(null),started=useRef(0),pauseAt=useRef(0),pausedMs=useRef(0),lastCue=useRef(0),lastBackup=useRef(0);
 const [exercise,setExercise]=useState(initialExercise),[stage,setStage]=useState<Stage>('idle'),[preview,setPreview]=useState(false),[phase,setPhase]=useState('Choose a movement and enable your camera.'),[metrics,setMetrics]=useState<PoseMeasurement|null>(null),[reps,setReps]=useState(0),[elapsed,setElapsed]=useState(0),[fps,setFps]=useState(0),[error,setError]=useState(''),[storageWarning,setStorageWarning]=useState(''),[mirror,setMirror]=useState(true),[overlay,setOverlay]=useState(true),[sound,setSound]=useState(audio),[deviceId,setDeviceId]=useState(''),[devices,setDevices]=useState<MediaDeviceInfo[]>([]),[recovery,setRecovery]=useState<SessionDraft|null>(null),[recovering,setRecovering]=useState(true),[checkResult,setCheckResult]=useState(''),[checkPose,setCheckPose]=useState<{image:Joint[];width:number;height:number}|null>(null);
 const overlayRef=useRef(overlay),soundRef=useRef(sound);overlayRef.current=overlay;soundRef.current=sound;
 const callbacks=useRef({onSaved,onActiveChange});callbacks.current={onSaved,onActiveChange};
 const active=stage==='tracking'||stage==='paused',starting=stage==='requesting'||stage==='loading',locked=active||starting||stage==='saving'||stage==='checking'||!!recovery||recovering;
 const clearOverlay=()=>{const c=canvas.current;if(c)c.getContext('2d')?.clearRect(0,0,c.width,c.height);};
 const release=()=>{running.current=false;cancelAnimationFrame(raf.current);abort.current?.abort();abort.current=null;detector.current?.close();detector.current=null;stopStream(stream.current);stream.current=null;if(video.current)video.current.srcObject=null;clearOverlay();window.speechSynthesis?.cancel();};
 const refreshDevices=async()=>{try{const list=await navigator.mediaDevices?.enumerateDevices();if(mounted.current)setDevices((list||[]).filter(d=>d.kind==='videoinput'));}catch{/* Labels become available after camera permission. */}};
 const activeTime=(now=performance.now())=>started.current?Math.max(0,((pausedRef.current?pauseAt.current:now)-started.current-pausedMs.current)/1000):0;
 const snapshot=():SessionDraft|null=>draft.current?{...draft.current,reps:counter.current.reps,duration:Math.round(activeTime()),frames:[...records.current]}:null;
 const persist=(value:SessionDraft|null)=>writeDraft(value).catch(()=>{if(mounted.current)setStorageWarning('Automatic recovery is unavailable in this browser. Finish and save, or download your recording before closing.');});
 const cue=(text:string,force=false)=>{if(!soundRef.current||!window.speechSynthesis||(!force&&performance.now()-lastCue.current<8000))return;lastCue.current=performance.now();window.speechSynthesis.cancel();const voice=new SpeechSynthesisUtterance(text);voice.rate=1;window.speechSynthesis.speak(voice);};
 useEffect(()=>{
  mounted.current=true;let alive=true;void refreshDevices();
  void readDraft().then(value=>{if(!alive)return;if(value&&value.frames.length>=2){draft.current=value;setRecovery(value);setExercise(value.exercise);setReps(value.reps);setStage('recovery');callbacks.current.onActiveChange(true);}}).catch(()=>{if(alive)setStorageWarning('Browser recovery storage is unavailable. You can still save sessions locally.');}).finally(()=>{if(alive)setRecovering(false);});
  const changed=()=>void refreshDevices();navigator.mediaDevices?.addEventListener('devicechange',changed);
  const hidden=()=>{if(document.hidden&&running.current&&!pausedRef.current)pauseSession(true);};document.addEventListener('visibilitychange',hidden);
  return()=>{alive=false;mounted.current=false;generation.current++;release();navigator.mediaDevices?.removeEventListener('devicechange',changed);document.removeEventListener('visibilitychange',hidden);callbacks.current.onActiveChange(false);};
 },[]);
 useEffect(()=>{if(checkPose&&sampleCanvas.current)draw(sampleCanvas.current,checkPose.image,checkPose.width,checkPose.height);},[checkPose]);
 const recover=(message:string)=>{
  const value=snapshot();generation.current++;release();operation.current=false;setPreview(false);setMetrics(null);setError(message);setPhase('Tracking stopped. Your recorded movement is safe.');
  if(value&&value.frames.length>=2){draft.current=value;setRecovery(value);setStage('recovery');void persist(value);callbacks.current.onActiveChange(true);}
  else{draft.current=null;setStage('idle');callbacks.current.onActiveChange(false);void persist(null);}
 };
 const pauseSession=(automatic=false)=>{
  if(!running.current||pausedRef.current)return;
  pausedRef.current=true;pauseAt.current=performance.now();pauseEpoch.current++;counter.current.resetPartial();tracker.current.reset();clearOverlay();setMetrics(null);setStage('paused');setPhase(automatic?'Paused because this page was hidden. Resume when you are ready.':'Paused. Resume from your starting position.');void persist(snapshot());
 };
 const resume=()=>{if(!running.current)return;pausedMs.current+=performance.now()-pauseAt.current;pausedRef.current=false;pauseEpoch.current++;tracker.current.reset();counter.current.resetPartial();setStage('tracking');setPhase('Return to the starting position.');};
 const cancel=()=>{generation.current++;release();operation.current=false;setPreview(false);setMetrics(null);setStage('idle');setPhase('Camera stopped. You can try again.');callbacks.current.onActiveChange(false);};
 const save=async(value:SessionDraft)=>{
  if(operation.current)return;operation.current=true;setStage('saving');setError('');callbacks.current.onActiveChange(true);draft.current=value;setRecovery(value);await persist(value);
  try{const session=await api<WorkoutSession>('/api/sessions',{method:'POST',body:JSON.stringify(value)});await persist(null);draft.current=null;if(mounted.current){setRecovery(null);operation.current=false;callbacks.current.onActiveChange(false);callbacks.current.onSaved(session);}}
  catch(e){if(mounted.current){operation.current=false;setStage('recovery');setError('Recording kept on this device. '+errorText(e));setPhase('Retry saving, or download a backup.');}}
 };
 const finish=async()=>{
  const value=snapshot();generation.current++;release();operation.current=false;setPreview(false);setMetrics(null);setElapsed(value?.duration||0);
  if(!value||value.frames.length<2){setStage('idle');callbacks.current.onActiveChange(false);setError('No reliable joint frames were recorded. Follow the framing message, or run the tracker check below.');void persist(null);return;}
  await save(value);
 };
 const discard=async()=>{await persist(null);draft.current=null;records.current=[];setRecovery(null);setStage('idle');setReps(0);setElapsed(0);setError('');setPhase('Ready for a new session.');if(lockExercise)setExercise(initialExercise);callbacks.current.onActiveChange(false);};
 const start=async()=>{
  if(operation.current||running.current||recovery)return;operation.current=true;
  const ticket=++generation.current;abort.current=new AbortController();const signal=abort.current.signal;
  setError('');setCheckResult('');setCheckPose(null);setStage('requesting');setPhase('Allow camera access in your browser…');callbacks.current.onActiveChange(true);
  try{
   const media=await openCamera(deviceId,signal);if(ticket!==generation.current){stopStream(media);return;}stream.current=media;setPreview(true);
   await playCamera(video.current!,media,signal);if(ticket!==generation.current)return;void refreshDevices();
   const track=media.getVideoTracks()[0];track.addEventListener('ended',()=>{if(ticket===generation.current)recover('The camera disconnected. Reconnect it and start a new session.');},{once:true});
   setStage('loading');setPhase('Camera connected. Loading the joint tracker…');const client=new PoseClient();detector.current=client;await client.start();if(ticket!==generation.current){client.close();return;}
   tracker.current.reset();counter.current=new RepCounter();records.current=[];started.current=performance.now();pausedMs.current=0;pausedRef.current=false;pauseEpoch.current++;lastBackup.current=0;
   draft.current={client_id:recordingId||crypto.randomUUID(),exercise,date:new Date().toISOString(),reps:0,duration:0,target,source:'camera',frames:[]};
   setReps(0);setElapsed(0);setFps(0);running.current=true;operation.current=false;setStage('tracking');setPhase('Find the starting position.');cue('Camera ready. Find your starting position.',true);
   let lastVideoTime=-1,lastFrameAt=performance.now(),lastUI=0,lastDetection=0,meanInterval=0,lastRecorded=-Infinity;
   const loop=async()=>{
    if(!running.current||ticket!==generation.current)return;
    const now=performance.now(),v=video.current!;
    try{
     if(!pausedRef.current&&v.readyState>=2&&v.currentTime!==lastVideoTime&&now-lastDetection>=50){
      lastVideoTime=v.currentTime;lastFrameAt=now;const epoch=pauseEpoch.current;
      const result=await client.detect(v,now);
      if(!running.current||ticket!==generation.current)return;
      if(epoch!==pauseEpoch.current||pausedRef.current){raf.current=requestAnimationFrame(()=>void loop());return;}
      const interval=lastDetection?now-lastDetection:0;if(interval)meanInterval=meanInterval?meanInterval*.8+interval*.2:interval;lastDetection=now;
      const update=tracker.current.update(exercise,result.image,result.world,now),m=update.measurement;
      if(canvas.current)draw(canvas.current,overlayRef.current?result.image:[],v.videoWidth,v.videoHeight);
      const counted=counter.current.update(m,now);
      const serializable=[result.image,result.world].every(list=>list.length===33&&list.every(p=>[p.x,p.y,p.z].every(Number.isFinite)));
      if(m&&serializable&&now-lastRecorded>=100&&records.current.length<3600){
       const clean=(j:Joint[])=>j.map(p=>({x:p.x,y:p.y,z:p.z,visibility:Math.max(0,Math.min(1,p.visibility??0))}));
       records.current.push({timestamp:Math.round(activeTime(now)*1000),image:clean(result.image),world:clean(result.world),width:v.videoWidth,height:v.videoHeight,metrics:m});lastRecorded=now;
      }
      if(counted)cue(counter.current.reps===target?(autoFinishAtTarget?'Target complete. Saving your movement. Take a rest.':'Target complete. Finish and save when you are ready.'):`Rep ${counter.current.reps}`,true);
      if(autoFinishAtTarget&&counter.current.reps>=target&&records.current.length>=2){setReps(counter.current.reps);void finish();return;}
      let instruction=update.message;
      if(m?.countable)instruction=counter.current.stage==='waiting'?`Show the starting position (${movementTargets[exercise].start}°).`:counter.current.stage==='target'?`Target reached. Return to the starting position (${movementTargets[exercise].start}°).`:m.rest?'Ready. '+movementTargets[exercise].description:movementTargets[exercise].description;
      if(now-lastUI>150){lastUI=now;setMetrics(m);setReps(counter.current.reps);setElapsed(activeTime(now));setPhase(instruction);setFps(meanInterval?Math.round(1000/meanInterval):0);}
      if(now-lastBackup.current>3000&&records.current.length>=2){lastBackup.current=now;void persist(snapshot());}
      if(records.current.length>=3600){void finish();return;}
     }else if(!pausedRef.current&&now-lastFrameAt>5000){throw new Error('The camera stopped sending video. Select another camera or close other apps using it.');}
     if(pausedRef.current)lastFrameAt=now;
     raf.current=requestAnimationFrame(()=>void loop());
    }catch(e){if(ticket===generation.current&&mounted.current)recover(errorText(e));}
   };
   void loop();
  }catch(e){if(ticket!==generation.current||!mounted.current)return;release();operation.current=false;setPreview(false);setStage('idle');setMetrics(null);setPhase('Camera setup needs attention.');setError(cameraError(e));callbacks.current.onActiveChange(false);}
 };
 // Only attempt automatic setup once per mounted routine step. Errors and cancellation
 // leave the camera off until the user explicitly retries. Recovery always comes first.
 useEffect(()=>{if(!autoStart||recovering||autoStartAttempted.current)return;autoStartAttempted.current=true;if(!recovery&&stage==='idle')void start();},[autoStart,recovering]);
 const checkTracker=async()=>{
  if(operation.current||running.current||recovery)return;operation.current=true;const ticket=++generation.current;setStage('checking');setError('');setCheckResult('Checking local joint detection with a bundled reference photo…');setCheckPose(null);callbacks.current.onActiveChange(true);
  const client=new PoseClient();detector.current=client;
  try{await client.start();const response=await fetch('/diagnostics/pose-model.png',{signal:AbortSignal.timeout(10000)});if(!response.ok)throw new Error('The reference photo is missing. Rebuild the app.');const bitmap=await createImageBitmap(await response.blob());const width=bitmap.width,height=bitmap.height;try{const result=await client.detect(bitmap,performance.now());if(ticket!==generation.current)return;if(result.image.length!==33||result.world.length!==33)throw new Error('The tracker loaded but did not find the reference person.');setCheckPose({image:result.image,width,height});setCheckResult(`Tracker check passed: ${result.image.length} image joints and ${result.world.length} 3D joints detected. ${Math.round(result.inferenceMs)} ms processing. This reference-photo check does not test your webcam or rep accuracy.`);}finally{bitmap.close();}}
  catch(e){if(ticket===generation.current)setCheckResult('Tracker check failed: '+errorText(e));}
  finally{client.close();if(ticket===generation.current){detector.current=null;operation.current=false;setStage('idle');callbacks.current.onActiveChange(false);}}
 };
 const angle=(n:number|null|undefined)=>typeof n==='number'&&Number.isFinite(n)?Math.round(n)+'°':'—';
 return <div className="training-layout studio-v2"><div className="capture-column">
  <div className="exercise-pills">{(Object.keys(exercises)as ExerciseType[]).map(id=><button key={id} disabled={locked||lockExercise} className={exercise===id?'selected':''} onClick={()=>{setExercise(id);setReps(0);setMetrics(null);setPhase(exercises[id].cue);}}>{exercises[id].name}</button>)}</div>
  <div className="camera-selector"><label htmlFor="camera-choice">Camera</label><select id="camera-choice" disabled={locked} value={deviceId} onChange={e=>setDeviceId(e.target.value)}><option value="">Default camera</option>{devices.filter(d=>d.deviceId).map((d,i)=><option key={d.deviceId} value={d.deviceId}>{d.label||`Camera ${i+1}`}</option>)}</select><button className="icon-button" disabled={locked} aria-label="Refresh cameras" onClick={()=>void refreshDevices()}><RefreshCw size={15}/></button></div>
  <div className="camera-card"><div className="camera-toolbar"><span><i className={metrics?.countable?'live-dot':'idle-dot'}/>{active?`${stage==='paused'?'PAUSED':'LIVE'} · ${fps} FPS`:'CAMERA STUDIO'}</span><div className="camera-tools"><button aria-label="Mirror camera" aria-pressed={mirror} onClick={()=>setMirror(!mirror)}><FlipHorizontal2 size={16}/></button><button aria-label="Show joint overlay" aria-pressed={overlay} onClick={()=>{setOverlay(!overlay);if(overlay)clearOverlay();}}><Layers size={16}/></button><button aria-label="Enable voice cues" aria-pressed={sound} onClick={()=>setSound(!sound)}>{sound?<Volume2 size={16}/>:<VolumeX size={16}/>}</button></div></div>
   <div className="camera-surface"><video ref={video} playsInline muted style={{visibility:preview?'visible':'hidden',transform:mirror?'scaleX(-1)':'none'}}/><canvas ref={canvas} style={{transform:mirror?'scaleX(-1)':'none'}}/>
    {!preview&&<div className="camera-placeholder"><div className="scan-icon"><ScanLine size={42}/></div><span className="eyebrow">YOUR PERSONAL MOVEMENT STUDIO</span><h3>{recovery?'Your recording is safe.':'See every movement.'}</h3><p>{recovery?'Save or download your recovered session below.':'Show your joints, follow the guide, and complete a full movement cycle.'}</p>{!recovery&&<button className="primary-button" disabled={locked} onClick={()=>void start()}>{starting||recovering?<LoaderCircle className="spin" size={17}/>:<Camera size={17}/>} {recovering?'Checking saved draft…':starting?'Connecting…':'Enable camera'}</button>}<small>Camera frames stay on this device. Only joint data is saved.</small></div>}
    {preview&&active&&<><div className="live-angle"><span>{exercises[exercise].joint.toUpperCase()} ANGLE</span><strong>{angle(metrics?.primary)}</strong><small>{metrics?.targetLabel||movementTargets[exercise].description}</small><em>{metrics?.trackingSide?`${metrics.trackingSide} side · ${Math.round(metrics.confidence*100)}% visibility`:'Finding required joints'}</em></div><div className="live-rep"><strong>{reps}</strong><span>of {target} reps</span></div></>}
    <div className={'camera-status '+(metrics?.peak?'target-reached':'')} role="status"><i className={metrics?.countable?'live-dot':'idle-dot'}/>{phase}</div>
    {stage==='paused'&&<div className="pause-overlay"><Pause size={36}/><span>Session paused</span><button className="primary-button" onClick={resume}>Resume tracking</button></div>}
   </div>
   <div className="camera-actions"><span><strong>{exercises[exercise].name}</strong><small>{exercises[exercise].cue}</small></span>{starting&&<button className="secondary-button" onClick={cancel}><X size={16}/> Cancel setup</button>}{active&&<div><button className="secondary-button" onClick={stage==='paused'?resume:()=>pauseSession()}>{stage==='paused'?<Play size={15}/>:<Pause size={15}/>} {stage==='paused'?'Resume':'Pause'}</button><button className="primary-button" onClick={()=>void finish()}><CameraOff size={15}/> Finish & save</button></div>}</div>
  </div>
  {error&&<div className="error-box" role="alert"><AlertCircle size={18}/><span>{error}</span></div>}
  {recovery&&<section className="recovery-card"><h3>{stage==='saving'?'Saving your movement…':'Unsaved session recovered'}</h3><p>{exercises[recovery.exercise].name} · {recovery.reps} reps · {recovery.frames.length} joint frames</p><div><button className="primary-button" disabled={stage==='saving'} onClick={()=>void save(recovery)}>{stage==='saving'?<LoaderCircle className="spin" size={16}/>:<Check size={16}/>} Save session</button><button className="secondary-button" onClick={()=>saveFile('motionai-recovered-session.json',recovery)}><Download size={16}/> Download backup</button><button className="text-button" disabled={stage==='saving'} onClick={()=>void discard()}>Discard draft</button></div></section>}
  {storageWarning&&<p className="page-footnote" role="status">{storageWarning}</p>}
  <div className="setup-checklist"><span className="eyebrow">BEFORE YOUR FIRST REP</span><div><span><Check size={15}/> {exercise==='push_up'?'Side view, body in a plank':'Required joints inside the frame'}</span><span><Check size={15}/> Start pose → target → return</span><span><Check size={15}/> Even lighting</span></div></div>
  <details className="tracker-diagnostics"><summary>Camera & tracking help</summary><p>Use Chrome or Edge at <a href="http://localhost:3000" target="_blank" rel="noreferrer">localhost:3000</a>. Allow camera permission, close apps using the webcam, and select the correct camera above. Keep the local app launcher running.</p><button className="secondary-button" disabled={locked} onClick={()=>void checkTracker()}>{stage==='checking'?<LoaderCircle size={16} className="spin"/>:<ScanLine size={16}/>} Check joint tracker without camera</button>{stage==='checking'&&<button className="text-button" onClick={cancel}>Cancel check</button>}{checkResult&&<p role="status">{checkResult}</p>}{checkPose&&<div className="diagnostic-image"><img src="/diagnostics/pose-model.png" alt="MediaPipe reference photo used only to verify detection"/><canvas ref={sampleCanvas}/></div>}<small>Reference photo: official Google MediaPipe sample. No session or repetitions are created by this check.</small></details>
 </div><aside className="coach-column"><MovementDemo exercise={exercise}/><div className="rep-card"><span className="eyebrow">COMPLETED REPS</span><strong>{String(reps).padStart(2,'0')}<em>/ {target}</em></strong><div className="progress-track"><i style={{width:Math.min(100,reps/target*100)+'%'}}/></div><div className="rep-meta"><span>{reps>=target?'Target reached':autoFinishAtTarget?'Saves at your target':'Full movement cycles'}</span><span>{formatTime(elapsed)}</span></div></div><section className="coach-card"><span className="eyebrow">YOUR LIVE MOVEMENT</span><h3>{metrics?.peak?'Target reached':metrics?.countable?'Joints are tracking':'Let’s find your position'}</h3><p>{metrics?.feedback||phase}</p><div className="joint-stats"><div><span>Left {exercises[exercise].joint.toLowerCase()}</span><strong>{angle(metrics?.left)}</strong></div><div><span>Right {exercises[exercise].joint.toLowerCase()}</span><strong>{angle(metrics?.right)}</strong></div></div><div className="bend-target"><strong>{movementTargets[exercise].description}</strong><div className="progress-track"><i style={{width:((metrics?.progress||0)*100)+'%'}}/></div><span>Start position: {movementTargets[exercise].start}°</span></div><small>Angles are estimates from detected joints. Hidden joints show a dash. Finish your session for MotionBERT 3D analysis.</small></section></aside></div>;
};
