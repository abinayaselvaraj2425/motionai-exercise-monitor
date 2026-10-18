// Component lifecycle checks with deterministic camera/model adapters. No real camera or user data.
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import assert from 'node:assert/strict';
const code=ts.transpileModule(fs.readFileSync('src/components/LiveCameraTracker.tsx','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
async function setup({draft,failSave=false,failCamera=false,autoFinishAtTarget=true,autoStart=true}={}){
 const state=[],effects=[],cleanups=[];let cursor=0,dirty=true,tree,now=1000,frameId=0;const frames=new Map();const log={opens:0,saves:[],saved:[],stops:0,closes:0,backups:[]};
 const same=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
 const react={useState(initial){const i=cursor++;state[i]??={value:initial};return[state[i].value,v=>{state[i].value=typeof v==='function'?v(state[i].value):v;dirty=true;}];},useRef(value){const i=cursor++;return state[i]??=( {current:value});},useEffect(fn,deps){const i=cursor++;if(!same(state[i]?.deps,deps)){state[i]={deps};effects.push(()=>{cleanups[i]?.();cleanups[i]=fn();});}}};
 const ctx=new Proxy({}, {get:()=>()=>{}});const video={readyState:4,currentTime:1,videoWidth:640,videoHeight:480};
 const jsx=(type,props)=>{if(props.ref&&type==='video')props.ref.current=video;if(props.ref&&type==='canvas')props.ref.current={width:640,height:480,getContext:()=>ctx};return{type,props};};
 const joint=()=>({x:.5,y:.5,z:0,visibility:1});
 class PoseClient{async start(){}async detect(){return {image:Array.from({length:33},joint),world:Array.from({length:33},joint),inferenceMs:10};}close(){log.closes++;}}
 class RepCounter{reps=0;stage='ready';update(){this.reps++;return true;}resetPartial(){}}
 class PoseTracker{reset(){}update(){return {measurement:{left:160,right:160,primary:160,countable:true,rest:true,visible:8,bodyAngle:170},message:'Test fixture'};}}
 const pose={PoseTracker,RepCounter,exercises:{squat:{name:'Squat',joint:'Knee',cue:'Show joints'}},movementTargets:{squat:{start:155,target:120,description:'Bend and return'}}};
 const data={api:async(url,options)=>{const value=JSON.parse(options.body);log.saves.push(value);if(failSave)throw Error('Test offline');return {...value,id:value.client_id,motionbert:null};},formatTime:String,saveFile(){}};
 const camera={openCamera:async()=>{log.opens++;if(failCamera)throw Error('Test camera denied');return {getVideoTracks:()=>[{addEventListener(){}}]};},playCamera:async()=>{},stopStream:s=>{if(s)log.stops++;},cameraError:e=>e.message,errorText:e=>e.message};
 const recovery={readDraft:async()=>draft,writeDraft:async value=>{log.backups.push(value);}};
 const module={exports:{}};const sandbox={module,exports:module.exports,require:id=>id==='react'?react:id==='react/jsx-runtime'?{jsx,jsxs:jsx}:id==='lucide-react'?new Proxy({},{get:(_,k)=>k}):id==='../pose'?pose:id==='../data'?data:id==='../camera'?camera:id==='../PoseClient'?{PoseClient}:id==='../draft'?recovery:id==='./MovementDemo'?{MovementDemo:()=>null}:null,performance:{now:()=>now},requestAnimationFrame:cb=>{frames.set(++frameId,cb);return frameId;},cancelAnimationFrame:id=>frames.delete(id),navigator:{mediaDevices:{enumerateDevices:async()=>[],addEventListener(){},removeEventListener(){}}},document:{hidden:false,addEventListener(){},removeEventListener(){}},window:{speechSynthesis:null},AbortController,crypto:{randomUUID:()=> '00000000-0000-4000-8000-000000000001'},console};
 vm.runInNewContext(code,sandbox);
 const props={initialExercise:'squat',target:3,audio:false,recordingId:'00000000-0000-4000-8000-000000000002',autoStart,autoFinishAtTarget,onSaved:s=>log.saved.push(s),onActiveChange(){}};
 async function flush(){for(let n=0;n<30;n++){await Promise.resolve();if(dirty){dirty=false;cursor=0;tree=module.exports.LiveCameraTracker(props);effects.splice(0).forEach(fn=>fn());}}}
 await flush();return {log,flush,async tick(){now+=150;video.currentTime+=.15;const pending=[...frames.values()];frames.clear();pending.forEach(cb=>cb());await flush();},dispose(){cleanups.forEach(fn=>fn?.());},tree:()=>tree};
}
let n=0;async function test(name,fn){await fn();n++;console.log('PASS',name);}
await test('routine opens camera once and saves/releases exactly at target',async()=>{const h=await setup();assert.equal(h.log.opens,1);await h.tick();await h.tick();assert.equal(h.log.saves.length,1);assert.equal(h.log.saves[0].reps,3);assert.equal(h.log.saved.length,1);assert.equal(h.log.saved[0].id,'00000000-0000-4000-8000-000000000002');assert.ok(h.log.stops>0);assert.ok(h.log.closes>0);await h.tick();assert.equal(h.log.saves.length,1);h.dispose();});
await test('failed target save preserves recording and never auto-retries camera',async()=>{const h=await setup({failSave:true});await h.tick();await h.tick();await h.tick();assert.equal(h.log.saves.length,1);assert.equal(h.log.saved.length,0);assert.equal(h.log.opens,1);assert.ok(h.log.backups.some(d=>d?.reps===3));assert.ok(h.log.stops>0);h.dispose();});
await test('existing recovery takes precedence over automatic camera startup',async()=>{const h=await setup({draft:{exercise:'squat',reps:2,frames:[{},{}]}});assert.equal(h.log.opens,0);h.dispose();});
await test('camera denial does not create an automatic permission retry loop',async()=>{const h=await setup({failCamera:true});await h.flush();assert.equal(h.log.opens,1);assert.equal(h.log.saves.length,0);h.dispose();});
await test('disabled auto-start leaves camera off',async()=>{const h=await setup({autoStart:false});assert.equal(h.log.opens,0);h.dispose();});
await test('ordinary studio does not automatically stop at its target',async()=>{const h=await setup({autoFinishAtTarget:false});await h.tick();await h.tick();await h.tick();assert.equal(h.log.saves.length,0);assert.equal(h.log.stops,0);h.dispose();});
console.log(n+' routine camera lifecycle checks passed');
