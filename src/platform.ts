import {api,SessionSummary} from './data';
export type User={id:string;username:string;provider:string};
export type AuthState={user:User|null;google:boolean;chat:boolean};
export type Metric={key:string;label:string;value:number|null;unit:string;description:string};
export type MovementReport={version:string;source:string;exercise:string;coverage:number;measured_cycles:number;metrics:Metric[];observations:string[];focus:string;method:{joint:string;convention:string;quality:string;limits:string};trajectories:{left:(number|null)[];right:(number|null)[];times:number[]};comparison:{previous:{id:string;date:string;metrics:Metric[]}[];changes:{key:string;delta:number}[];note:string}};
export const dayKey=(date:Date|string)=>{const d=new Date(date);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
export const dateText=(date:string)=>new Date(date).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'});
export function bounds(date:string,period:'day'|'week'|'month'){
 const start=new Date(date+'T00:00:00');
 if(period==='week')start.setDate(start.getDate()-((start.getDay()+6)%7));
 if(period==='month')start.setDate(1);
 const end=new Date(start);if(period==='month')end.setMonth(end.getMonth()+1);else end.setDate(end.getDate()+(period==='week'?7:1));
 return {start,end,query:new URLSearchParams({start:start.toISOString(),end:end.toISOString()}).toString()};
}
export const within=(s:SessionSummary,start:Date,end:Date)=>new Date(s.date)>=start&&new Date(s.date)<end;
export async function downloadExport(query:string,format:'json'|'csv'){
 const response=await fetch('/api/export?'+query+'&format='+format);
 if(!response.ok){const error=await response.json();throw new Error(error.detail||'Export failed.');}
 const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`motionai-${dayKey(new Date())}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export const errorMessage=(e:unknown)=>e instanceof Error?e.message:'Something went wrong. Please retry.';
