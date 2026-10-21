import { ExerciseType, Joint } from './pose';
export interface RecordedFrame { timestamp:number; image:Joint[]; world:Joint[]; width:number; height:number; metrics:{left:number|null;right:number|null;primary:number;feedback:string;rest:boolean;peak:boolean;visible:number;bodyAngle:number|null;leftReliable?:boolean;rightReliable?:boolean}; }
export interface MotionResult { status:'complete'; model:string; checkpoint_sha256:string; parameters:number; latency_ms:number; input_shape:number[]; windows:number; frames:number[][][]; trajectories:{left:number[];right:number[]}; stats:{left_min:number;left_max:number;right_min:number;right_max:number;left_rom:number;right_rom:number;mean_difference:number}; mapping_notes:string[]; }
export interface WorkoutSession { id:string; exercise:ExerciseType; date:string; reps:number; duration:number; target:number; source:'camera'|'import'; frames:RecordedFrame[]; motionbert:MotionResult|null; }
export type SessionSummary = Omit<WorkoutSession,'frames'|'motionbert'> & {frame_count:number;analyzed:boolean;};
export interface Profile { name:string; weeklyGoal:number; repTarget:number; audio:boolean; goal?:string; onboarded?:boolean; reducedMotion?:boolean; theme?:'system'|'light'|'dark'; avatar?:string; accent?:'lime'|'cyan'|'violet'|'coral'; density?:'comfortable'|'compact'; motionLevel?:'full'|'soft'|'off'; homeWidgets?:string[]; }
export interface Health { status:string; motionbert:{loaded:boolean;name:string;error:string|null;parameters:number;checkpoint_sha256:string|null;}; }
export async function api<T>(url:string,options:RequestInit={}):Promise<T> {
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),url.endsWith('/analyze')?180000:url==='/api/chat'?60000:30000);
 try {
  const response=await fetch(url,{...options,signal:options.signal||controller.signal,headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('The local service returned an unexpected page. Start MotionAI and reload this tab.');
  const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:response.status===422?'Please check the highlighted fields and try again.':'Request failed. Please try again.');return value;
 } catch(error) {
  if(controller.signal.aborted)throw new Error('MotionAI took too long to respond. Retry shortly; if running locally, keep the app launcher open.');
  if(error instanceof TypeError){const local=typeof location==='undefined'||['localhost','127.0.0.1','::1'].includes(location.hostname);throw new Error(local?'Cannot reach the local service. Run START_APP.bat, then retry. Your unsaved session can be downloaded as a backup.':'Cannot reach MotionAI. Check your connection and retry. Your unsaved recording can be downloaded as a backup.');}
  throw error;
 } finally {clearTimeout(timer);}
}
export function displayAngle(value:unknown){return typeof value==='number'&&Number.isFinite(value)?Math.round(value)+'°':'—';}
export function cameraStats(frames:RecordedFrame[]) {
 const valid=(value:number|null):value is number=>value!==null&&Number.isFinite(value);
 const left=frames.map(f=>f.metrics.leftReliable===false?null:f.metrics.left).filter(valid),right=frames.map(f=>f.metrics.rightReliable===false?null:f.metrics.right).filter(valid);
 const paired=frames.filter(f=>valid(f.metrics.left)&&valid(f.metrics.right)&&f.metrics.leftReliable!==false&&f.metrics.rightReliable!==false).map(f=>Math.abs(f.metrics.left!-f.metrics.right!));
 const min=(v:number[])=>v.length?Math.min(...v):null,max=(v:number[])=>v.length?Math.max(...v):null,rom=(v:number[])=>v.length>1?Math.max(...v)-Math.min(...v):null;
 return {left_min:min(left),left_max:max(left),right_min:min(right),right_max:max(right),left_rom:rom(left),right_rom:rom(right),mean_difference:paired.length?paired.reduce((s,v)=>s+v,0)/paired.length:null};
}
export function formatTime(seconds:number) { const n=Math.max(0,Math.round(seconds));return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`; }
export function saveFile(name:string,data:unknown) {const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export function summary(session:WorkoutSession):SessionSummary { const {frames,motionbert,...rest}=session; return {...rest,frame_count:frames.length,analyzed:!!motionbert}; }
export function cameraSkeleton(p:Joint[]) {
 const at=(i:number)=>[p[i].x,-p[i].y,-p[i].z];const mid=(a:number[],b:number[])=>a.map((v,i)=>(v+b[i])/2);
 const hip=mid(at(23),at(24)),neck=mid(at(11),at(12));
 return [hip,at(24),at(26),at(28),at(23),at(25),at(27),mid(hip,neck),neck,at(0),mid(at(7),at(8)),at(11),at(13),at(15),at(12),at(14),at(16)];
}
