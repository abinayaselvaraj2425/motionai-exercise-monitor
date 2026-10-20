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
const {Login,Onboarding,ProgressHub,RoutineReport,HelpPage,CoachingFeedback,HomeDashboard}=await import(pathToFileURL(path.resolve(output)).href);
const profile={name:'Athlete',weeklyGoal:3,repTarget:10,audio:false,onboarded:false};
const cases=[['login',Login,{auth:{user:null,google:false,chat:false},onLogin(){}} ,'Create an account'],['onboarding',Onboarding,{profile,onDone(){}},'Your pace. Your space.'],['progress',ProgressHub,{sessions:[],runs:[],onOpen(){},onRoutine(){}},'No sessions yet'],['routine report',RoutineReport,{run:{id:'test',name:'Standing reset',date:'2026-10-19T12:00:00Z',ended:null,steps:[],reps:0,duration:0,complete:false},onOpen(){},onBack(){}},'Every step has its own story.'],['help',HelpPage,{},'What does MotionBERT do?']];
for(const [name,Component,props,text]of cases){const html=renderToStaticMarkup(React.createElement(Component,props));assert.ok(html.includes(text),name);assert.ok(!html.includes('undefined'),name);console.log('PASS:',name,'renders');}
const feedback=renderToStaticMarkup(React.createElement(CoachingFeedback,{report:{coaching:{summary:'We saw a repeatable movement.',cards:[{key:'lean',title:'Lift your chest a little',observed:'Your upper body leaned forward.',action:'Try a smaller comfortable bend.',evidence:'Visible for 40% of tracked time.',kind:'observed'},{key:'practice',title:'Practice at your pace',observed:'A guide, not a detected fault.',action:'Keep your feet planted.',evidence:'Exercise guide.',kind:'practice'}],next_session:['Try a smaller comfortable bend.'],scope:'Estimated visible positions.'}}}));
for(const text of ['How to improve your next set.','Try a smaller comfortable bend.','From your recording','Practice guide','For your next session'])assert.ok(feedback.includes(text),text);
assert.equal(renderToStaticMarkup(React.createElement(CoachingFeedback,{report:{}})),'');
console.log('PASS: plain-language coaching and legacy report compatibility');
const home=renderToStaticMarkup(React.createElement(HomeDashboard,{profile:{...profile,name:'Harini',homeWidgets:['progress','reports','overview','studio']},sessions:[],runs:[],weekCount:0,activeDays:0,totalReps:0,seconds:0,go(){},open(){},openRoutine(){}}));
for(const text of ['Hello, Harini','Start an','exercise.','routine.','No sessions yet'])assert.ok(home.includes(text),text);
const filtered=renderToStaticMarkup(React.createElement(HomeDashboard,{profile:{...profile,homeWidgets:['progress']},sessions:[],runs:[],weekCount:0,activeDays:0,totalReps:0,seconds:0,go(){},open(){},openRoutine(){}}));assert.ok(!filtered.includes('No sessions yet. Your findings will appear here.'));
const styles=['index.css','theme.css','studio.css'].map(f=>fs.readFileSync('src/'+f,'utf8')).join('\n');
fs.writeFileSync('tests/.test-data/home-preview.html','<!doctype html><html data-theme="light"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MotionAI home preview</title><style>'+styles+'</style><body><main class="workspace-main">'+home+'</main></body></html>');
console.log('PASS: actual Home, empty states and personalised shortcuts');
console.log('7 screen render checks passed. Browser and responsive layout review remain separate.');
