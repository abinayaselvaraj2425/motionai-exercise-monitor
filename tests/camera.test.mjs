import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const load=async path=>{
 const code=ts.transpileModule(fs.readFileSync(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
 return import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
};
const {openCamera,playCamera,cameraError}=await load('../src/camera.ts');
const {PoseClient}=await load('../src/PoseClient.ts');
const {cameraStats,api}=await load('../src/data.ts');
const browser={isSecureContext:true,Worker:true,createImageBitmap:true,OffscreenCanvas:true};
globalThis.window=browser;
let getMedia;Object.defineProperty(globalThis,'navigator',{value:{mediaDevices:{getUserMedia:(c)=>getMedia(c)}},configurable:true});
let passed=0;const test=async(name,fn)=>{await fn();passed++;console.log('PASS:',name);};
function fakeStream(){let stopped=0;return {getTracks:()=>[{stop:()=>stopped++}],stopped:()=>stopped};}
await test('late permission approval is released after cancellation',async()=>{
 let grant;getMedia=()=>new Promise(resolve=>grant=resolve);const controller=new AbortController();const pending=openCamera('',controller.signal);controller.abort();await assert.rejects(pending,/cancelled/);
 const stream=fakeStream();grant(stream);await new Promise(r=>setImmediate(r));assert.equal(stream.stopped(),1);
});
await test('camera permission error retains actionable browser guidance',async()=>{
 getMedia=async()=>{throw new DOMException('denied','NotAllowedError');};await assert.rejects(openCamera('',new AbortController().signal),e=>cameraError(e).includes('Allow camera access'));
});
await test('unsupported preferred resolution retries without restrictive settings',async()=>{
 let calls=[];const stream=fakeStream();getMedia=async c=>{calls.push(c);if(calls.length===1)throw new DOMException('size','OverconstrainedError');return stream;};assert.equal(await openCamera('',new AbortController().signal),stream);assert.equal(calls[1].video,true);assert.equal(stream.stopped(),0);
});
await test('cancelled video setup settles instead of hanging',async()=>{
 const controller=new AbortController();const video={play:()=>Promise.resolve(),readyState:0,videoWidth:0,videoHeight:0};const pending=playCamera(video,fakeStream(),controller.signal);controller.abort();await assert.rejects(pending,/cancelled/);
});
let worker;
class FakeWorker{constructor(){worker=this;this.messages=[];this.terminated=false;}postMessage(data){this.messages.push(data);}terminate(){this.terminated=true;}respond(data){this.onmessage({data});}}
globalThis.Worker=FakeWorker;
await test('closing detector cancels loading and terminates its worker',async()=>{
 const client=new PoseClient();const pending=client.start();client.close();await assert.rejects(pending,/stopped/);assert.equal(worker.terminated,true);
});
await test('worker startup failures surface a useful error and release resources',async()=>{
 const client=new PoseClient();const pending=client.start();worker.onerror();await assert.rejects(pending,/Could not load/);assert.equal(worker.terminated,true);
});
await test('inference result is real worker data and frame bitmap is released',async()=>{
 const client=new PoseClient();const pending=client.start();worker.respond({id:1,ready:true});await pending;let closed=0;globalThis.createImageBitmap=async()=>({close:()=>closed++});const detecting=client.detect({},1000);await new Promise(r=>setImmediate(r));worker.respond({id:2,image:[{x:.2,y:.3,z:.1}],world:[],inferenceMs:17});const result=await detecting;assert.equal(result.image[0].x,.2);assert.equal(result.inferenceMs,17);assert.equal(closed,1);client.close();
});
await test('hidden side measurements stay unavailable in reports, not zero degrees',async()=>{
 const data=[{metrics:{left:170,right:null,leftReliable:true,rightReliable:false}},{metrics:{left:110,right:null,leftReliable:true,rightReliable:false}}];const stats=cameraStats(data);assert.equal(stats.left_rom,60);assert.equal(stats.right_rom,null);assert.equal(stats.right_min,null);assert.equal(stats.mean_difference,null);
});
await test('offline saves and unexpected HTML produce readable recovery errors',async()=>{
 const original=globalThis.fetch;globalThis.fetch=async()=>{throw new TypeError('fetch failed');};await assert.rejects(api('/api/sessions'),/START_APP.bat/);globalThis.fetch=async()=>new Response('<html/>',{headers:{'content-type':'text/html'}});await assert.rejects(api('/api/sessions'),/unexpected page/);globalThis.fetch=original;
});
console.log(`${passed} camera lifecycle and recovery checks passed.`);
