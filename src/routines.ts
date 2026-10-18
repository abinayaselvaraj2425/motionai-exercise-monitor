import type { ExerciseType } from './pose';
export interface RoutineStep { key:string;name:string;cue?:string;seconds?:number;exercise?:ExerciseType;target?:number; }
export interface RoutineTemplate { id:string;name:string;tag:string;description:string;steps:RoutineStep[]; }
export interface RunStep extends RoutineStep {status:'pending'|'done'|'partial'|'skipped'|'missing';recording_id:string;session_id?:string;reps?:number;duration?:number;}
export interface RoutineRun {id:string;template:string;name:string;date:string;ended:string|null;steps:RunStep[];reps:number;duration:number;complete:boolean;}
