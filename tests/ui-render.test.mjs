// Render key screens with React's server renderer. This is not browser/layout verification.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import assert from 'node:assert/strict';
import {rollup} from 'rollup';
import {nodeResolve} from '@rollup/plugin-node-resolve';
import {renderToStaticMarkup} from 'react-dom/server';
import React from 'react';
const bundle=await rollup({input:'tests/ui-render-entry.ts',external:id=>/^(react|react-dom|lucide-react|three)(\/|$)/.test(id),plugins:[{name:'typescript',transform(code,id){if(/\.tsx?$/.test(id))return ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;}},nodeResolve({extensions:['.js','.ts','.tsx']})]});
const output='tests/.test-data/ui-render.mjs';fs.mkdirSync(path.dirname(output),{recursive:true});await bundle.write({file:output,format:'es'});await bundle.close();
globalThis.location={search:''};
const {Login,Onboarding,ProgressHub,RoutineReport,HelpPage}=await import(pathToFileURL(path.resolve(output)).href);
const profile={name:'Athlete',weeklyGoal:3,repTarget:10,audio:false,onboarded:false};
const cases=[['login',Login,{auth:{user:null,google:false,chat:false},onLogin(){}} ,'Create an account'],['onboarding',Onboarding,{profile,onDone(){}},'Your pace. Your space.'],['progress',ProgressHub,{sessions:[],runs:[],onOpen(){},onRoutine(){}},'No sessions yet'],['routine report',RoutineReport,{run:{id:'test',name:'Standing reset',date:'2026-10-19T12:00:00Z',ended:null,steps:[],reps:0,duration:0,complete:false},onOpen(){},onBack(){}},'Every step has its own story.'],['help',HelpPage,{},'What does MotionBERT do?']];
for(const [name,Component,props,text]of cases){const html=renderToStaticMarkup(React.createElement(Component,props));assert.ok(html.includes(text),name);assert.ok(!html.includes('undefined'),name);console.log('PASS:',name,'renders');}
console.log('5 screen render checks passed. Browser and responsive layout review remain separate.');
