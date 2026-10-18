import React,{useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Play,Pause,RotateCcw } from 'lucide-react';
interface Props { label?:string;connections?:number[][];frames:number[][][];fps?:number;timestamps?:number[];highlightRegions?:string[];currentRepetitionBottomFrame?:number;onFrameChange?:(index:number)=>void; }
const bones=[[0,1],[1,2],[2,3],[0,4],[4,5],[5,6],[0,7],[7,8],[8,9],[9,10],[8,11],[11,12],[12,13],[8,14],[14,15],[15,16]];
export const SkeletonViewer:React.FC<Props>=({frames,connections,label='Estimated 3D skeleton',fps=20,timestamps,onFrameChange,currentRepetitionBottomFrame})=>{
 const mount=useRef<HTMLDivElement>(null),frame=useRef(0),playing=useRef(true),speed=useRef(1),clock=useRef(0),reset=useRef(()=>{});
 const [index,setIndex]=useState(0),[isPlaying,setPlaying]=useState(true),[playbackSpeed,setSpeed]=useState(1),[error,setError]=useState('');
 const times=timestamps?.length===frames.length?timestamps:frames.map((_,i)=>i*1000/fps);
 const timesRef=useRef(times),callbackRef=useRef(onFrameChange);timesRef.current=times;callbackRef.current=onFrameChange;
 useEffect(()=>{playing.current=isPlaying;speed.current=playbackSpeed;},[isPlaying,playbackSpeed]);
 useEffect(()=>{if(currentRepetitionBottomFrame!==undefined&&currentRepetitionBottomFrame<frames.length){frame.current=currentRepetitionBottomFrame;setIndex(frame.current);clock.current=timesRef.current[frame.current]-timesRef.current[0];setPlaying(false);}},[currentRepetitionBottomFrame,frames.length]);
 useEffect(()=>{
 const container=mount.current;if(!container||!frames.length)return;
 let renderer:THREE.WebGLRenderer;try{renderer=new THREE.WebGLRenderer({antialias:true});}catch{setError('3D rendering is unavailable in this browser. Joint-angle charts and exports are still available.');return;}
 const activeBones=connections||bones;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#142b26');
 const camera=new THREE.PerspectiveCamera(42,1,.01,100);camera.position.set(1.7,1.2,2.4);
 const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.7,0);controls.enableDamping=true;controls.minDistance=1;controls.maxDistance=6;
 renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));container.appendChild(renderer.domElement);
 scene.add(new THREE.AmbientLight(0xffffff,2));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(2,4,3);scene.add(light);
 const grid=new THREE.GridHelper(6,24,0x48685f,0x27473d);scene.add(grid);
 const jointGeo=new THREE.SphereGeometry(.025,12,12),boneGeo=new THREE.CylinderGeometry(.012,.012,1,8),jointMat=new THREE.MeshStandardMaterial({color:0xc2edda}),boneMat=new THREE.MeshStandardMaterial({color:0x89b5a6});
 const joints=Array.from({length:frames[0].length},()=>{const m=new THREE.Mesh(jointGeo,jointMat);scene.add(m);return m;});
 const limbs=activeBones.map(()=>{const m=new THREE.Mesh(boneGeo,boneMat);scene.add(m);return m;});
 const bounds=new THREE.Box3();frames.forEach(f=>f.forEach(p=>bounds.expandByPoint(new THREE.Vector3(p[0],p[1],p[2])))); const minY=bounds.min.y; const center=bounds.getCenter(new THREE.Vector3()); center.y-=minY; const radius=Math.max(.3,bounds.getSize(new THREE.Vector3()).length()/2);
 const offset=-minY+.03;const axis=new THREE.Vector3(0,1,0),direction=new THREE.Vector3();
 const fit=()=>{const angle=Math.min(THREE.MathUtils.degToRad(camera.fov/2),Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*camera.aspect));const distance=radius/Math.sin(angle)*1.15;controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(1,.35,1.6).normalize().multiplyScalar(distance));controls.minDistance=radius*.9;controls.maxDistance=distance*3;controls.update();}; const observer=new ResizeObserver(()=>{const w=container.clientWidth,h=container.clientHeight;if(w&&h){renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();fit();}});observer.observe(container);
 reset.current=fit;
 frame.current=0;clock.current=0;setIndex(0);let animation=0,last=performance.now(),displayed=-1;
 const render=(now:number)=>{
   const delta=Math.min(250,now-last);last=now;
   if(playing.current&&frames.length>1){const t=timesRef.current,total=t.at(-1)!-t[0]+1000/fps;clock.current=(clock.current+delta*speed.current)%total;let low=0,high=t.length-1;while(low<high){const mid=Math.ceil((low+high)/2);if(t[mid]-t[0]<=clock.current)low=mid;else high=mid-1;}frame.current=low;}
   if(displayed!==frame.current){displayed=frame.current;const data=frames[displayed];data.forEach((p,i)=>{if(i<joints.length)joints[i].position.set(p[0],p[1]+offset,p[2]);});activeBones.forEach(([a,b],i)=>{const start=joints[a].position,end=joints[b].position;direction.subVectors(end,start);const length=direction.length();limbs[i].visible=length>1e-6;limbs[i].scale.set(1,length,1);limbs[i].position.copy(start).add(end).multiplyScalar(.5);if(length>1e-6)limbs[i].quaternion.setFromUnitVectors(axis,direction.clone().normalize());});setIndex(displayed);callbackRef.current?.(displayed);}
   controls.update();renderer.render(scene,camera);animation=requestAnimationFrame(render);
 };
 animation=requestAnimationFrame(render);
 return()=>{cancelAnimationFrame(animation);observer.disconnect();controls.dispose();jointGeo.dispose();boneGeo.dispose();jointMat.dispose();boneMat.dispose();grid.geometry.dispose();const materials=Array.isArray(grid.material)?grid.material:[grid.material];materials.forEach(m=>m.dispose());renderer.dispose();renderer.domElement.remove();};
 },[frames,fps,connections]);
 const scrub=(value:number)=>{frame.current=value;clock.current=timesRef.current[value]-timesRef.current[0];setIndex(value);};
 return <div className="skeleton-viewer">{error?<div className="viewer-error" role="status">{error}</div>:<div ref={mount} className="viewer-canvas"/>}<div className="viewer-hud"><span>{label.toUpperCase()}</span><button className="viewer-button" onClick={()=>reset.current()}><RotateCcw size={13}/> Reset view</button></div><div className="viewer-controls"><input aria-label="Movement replay timeline" type="range" min={0} max={Math.max(0,frames.length-1)} value={index} onChange={e=>scrub(Number(e.target.value))}/><div><span><button className="viewer-button" onClick={()=>setPlaying(!isPlaying)}>{isPlaying?<Pause size={14}/>:<Play size={14}/>} {isPlaying?'Pause':'Play'}</button><button className="viewer-button" aria-label="Restart movement replay" onClick={()=>scrub(0)}><RotateCcw size={14}/></button><small>Frame {index+1} / {frames.length}</small></span><span>{[.25,.5,1].map(n=><button className={'viewer-button '+(playbackSpeed===n?'selected':'')} key={n} onClick={()=>setSpeed(n)}>{n}×</button>)}</span></div></div></div>;
};

