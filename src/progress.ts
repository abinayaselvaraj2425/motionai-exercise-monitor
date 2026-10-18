import type { SessionSummary } from './data';
export type Period='day'|'week'|'month';
export function startOf(date:Date,period:Period){const d=new Date(date);d.setHours(0,0,0,0);if(period==='week')d.setDate(d.getDate()-(d.getDay()+6)%7);if(period==='month')d.setDate(1);return d;}
export function shift(date:Date,period:Period,amount:number){const d=new Date(date);if(period==='month')d.setMonth(d.getMonth()+amount,1);else d.setDate(d.getDate()+amount*(period==='week'?7:1));return d;}
export function dayKey(d:Date){return `${d.getFullYear()}-${d.getMonth()+1}-${d.getDate()}`;}
export function totals(sessions:SessionSummary[],start:Date,end:Date){const rows=sessions.filter(s=>{const t=new Date(s.date).getTime();return t>=+start&&t<+end;});return {reps:rows.reduce((n,s)=>n+s.reps,0),duration:rows.reduce((n,s)=>n+s.duration,0),recordings:rows.length,days:new Set(rows.map(s=>dayKey(new Date(s.date)))).size};}
export function change(current:number,previous:number){if(previous===0)return current===0?'No activity in either period':'New activity · no previous baseline';const pct=(current-previous)/previous*100;return Math.abs(pct)<.05?'Unchanged':`${Math.abs(pct).toFixed(1).replace(/\.0$/,'')}% ${pct>0?'more':'less'}`;}
export function compare(sessions:SessionSummary[],period:Period,offset=0,now=new Date()){
 const start=shift(startOf(now,period),period,offset),fullEnd=shift(start,period,1),previousStart=shift(start,period,-1);
 const end=offset===0?new Date(now):fullEnd;
 let previousEnd=new Date(start);
 if(offset===0){
  // Match local calendar position and time, rather than UTC milliseconds (DST safe).
  const days=period==='month'?now.getDate()-1:period==='week'?(now.getDay()+6)%7:0;
  previousEnd=new Date(previousStart);previousEnd.setDate(previousEnd.getDate()+days);previousEnd.setHours(now.getHours(),now.getMinutes(),now.getSeconds(),now.getMilliseconds());
  if(previousEnd>start)previousEnd=new Date(start);
 }
 return {start,end,previousStart,previousEnd,current:totals(sessions,start,end),previous:totals(sessions,previousStart,previousEnd),partial:offset===0};
}
