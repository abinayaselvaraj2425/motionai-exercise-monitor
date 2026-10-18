import React, { useEffect, useId, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { exercises, ExerciseType, movementTargets } from '../pose';

type Point = [number, number];
type DemoPose = {
  points: Record<string, Point>;
  paths: string[][];
  secondary: string[][];
  measured: [string, string, string];
};
const radians = (degrees: number) => degrees * Math.PI / 180;
const from = (origin: Point, length: number, degrees: number): Point => [origin[0] + length * Math.cos(radians(degrees)), origin[1] + length * Math.sin(radians(degrees))];
const between = (a: Point, b: Point, t: number): Point => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

/** Illustration geometry only. These points never enter camera measurements or session data. */
export function demoPose(exercise: ExerciseType, amount: number): DemoPose {
  const bend = Math.max(0, Math.min(1, amount));
  if (exercise === 'squat' || exercise === 'lunge') {
    const knee: Point = [exercise === 'lunge' ? 176 : 137, 164];
    const ankle: Point = [knee[0], 216];
    const hip = from(knee, 53, -85 - 70 * bend);
    const shoulder: Point = [hip[0] + (exercise === 'squat' ? 20 * bend : 0), hip[1] - 53];
    const points: Record<string, Point> = {
      head: [shoulder[0], shoulder[1] - 22], shoulder, hip, knee, ankle,
      toe: [ankle[0] + 18, ankle[1]],
      elbow: [shoulder[0] + 25, shoulder[1] + 20],
      wrist: [shoulder[0] + 51, shoulder[1] + 12],
    };
    const secondary: string[][] = [];
    if (exercise === 'lunge') {
      const rearAnkle: Point = [168 - 111 * bend, 216];
      const middle = between(hip, rearAnkle, .5);
      const dx = rearAnkle[0] - hip[0], dy = rearAnkle[1] - hip[1];
      const distance = Math.hypot(dx, dy);
      const offset = Math.sqrt(Math.max(0, 52.5 ** 2 - distance ** 2 / 4));
      points.rearKnee = [middle[0] + dy / distance * offset, middle[1] - dx / distance * offset];
      points.rearAnkle = rearAnkle;
      points.rearToe = [rearAnkle[0] + 17, rearAnkle[1]];
      secondary.push(['hip', 'rearKnee', 'rearAnkle', 'rearToe']);
    }
    return { points, paths: [['head', 'shoulder', 'hip', 'knee', 'ankle', 'toe'], ['shoulder', 'elbow', 'wrist']], secondary, measured: ['hip', 'knee', 'ankle'] };
  }
  if (exercise === 'push_up') {
    const degrees = 170 - 75 * bend, length = 38;
    const wrist: Point = [65, 216];
    const shoulder: Point = [65, 216 - 2 * length * Math.sin(radians(degrees / 2))];
    const elbow: Point = [65 + length * Math.cos(radians(degrees / 2)), (shoulder[1] + wrist[1]) / 2];
    const ankle: Point = [224, 216];
    // Shoulder, hip and ankle remain collinear throughout the movement.
    const points: Record<string, Point> = {
      head: between(shoulder, ankle, -.13), shoulder,
      hip: between(shoulder, ankle, .44), knee: between(shoulder, ankle, .75), ankle,
      toe: [239, 216], elbow, wrist,
    };
    return { points, paths: [['head', 'shoulder', 'hip', 'knee', 'ankle', 'toe'], ['shoulder', 'elbow', 'wrist']], secondary: [], measured: ['shoulder', 'elbow', 'wrist'] };
  }
  const shoulder: Point = [105, 91], hip: Point = [114, 150];
  let elbow: Point, wrist: Point;
  if (exercise === 'shoulder_press') {
    // Flexed elbows at shoulder height, then extend both arms overhead.
    elbow = from(shoulder, 38, 180 + 70 * bend);
    wrist = from(elbow, 36, 270 - 10 * bend);
  } else {
    elbow = from(shoulder, 35, 100 + 158 * bend);
    wrist = from(elbow, 36, 100 + 158 * bend);
  }
  const ankle: Point = [114 - (exercise === 'jumping_jack' ? 45 * bend : 0), 216];
  const points: Record<string, Point> = {
    head: [130, 62], neck: [130, 86], shoulder, hip,
    centerHip: [130, 150], elbow, wrist,
    knee: between(hip, ankle, .52), ankle, toe: [ankle[0] - 15, 216],
  };
  for (const id of ['shoulder', 'hip', 'elbow', 'wrist', 'knee', 'ankle', 'toe']) {
    points['right' + id] = [260 - points[id][0], points[id][1]];
  }
  return {
    points,
    paths: [['head', 'neck', 'centerHip'], ['shoulder', 'rightshoulder'], ['hip', 'righthip'], ['shoulder', 'elbow', 'wrist'], ['hip', 'knee', 'ankle', 'toe']],
    secondary: [['rightshoulder', 'rightelbow', 'rightwrist'], ['righthip', 'rightknee', 'rightankle', 'righttoe']],
    measured: exercise === 'shoulder_press' ? ['shoulder', 'elbow', 'wrist'] : ['hip', 'shoulder', 'elbow'],
  };
}

export function demoAngle(pose: DemoPose) {
  const [a, b, c] = pose.measured.map(name => pose.points[name]);
  const ux = a[0] - b[0], uy = a[1] - b[1], vx = c[0] - b[0], vy = c[1] - b[1];
  return Math.acos(Math.max(-1, Math.min(1, (ux * vx + uy * vy) / (Math.hypot(ux, uy) * Math.hypot(vx, vy))))) * 180 / Math.PI;
}

function rangeText(exercise: ExerciseType) {
  const target = movementTargets[exercise];
  if (exercise === 'shoulder_press') return `Bend elbows to ${target.start}° or less → extend above ${target.target}° overhead → bend again.`;
  if (exercise === 'jumping_jack') return `Arms below ${target.start}°, feet together → arms above ${target.target}°, feet apart → close.`;
  return `Start above ${target.start}° → bend to ${target.target}° or less → return above ${target.start}°.`;
}

export function MovementDemo({ exercise }: { exercise: ExerciseType }) {
  const [t, setT] = useState(0);
  const [play, setPlay] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const elapsed = useRef(0);
  const gridId = useId().replaceAll(':', '');
  useEffect(() => { elapsed.current = 0; setT(0); }, [exercise]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const changed = () => { if (preference.matches) setPlay(false); };
    preference.addEventListener('change', changed);
    return () => preference.removeEventListener('change', changed);
  }, []);
  useEffect(() => {
    if (!play) return;
    let raf = 0, previous = performance.now(), lastPaint = previous;
    const loop = (now: number) => {
      // Do not jump through a rep after the tab resumes from the background.
      elapsed.current += Math.min(100, now - previous); previous = now;
      if (now - lastPaint >= 32) { setT((elapsed.current % 4800) / 4800); lastPaint = now; }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [play, exercise]);
  const bend = (1 - Math.cos(t * Math.PI * 2)) / 2;
  const pose = demoPose(exercise, bend);
  const degrees = Math.round(demoAngle(pose));
  const activeJoint = pose.points[pose.measured[1]];
  const step = bend < .08 ? '1 · Starting position' : bend > .92 ? '2 · Target reached' : t < .5 ? 'Move towards the target' : '3 · Return to start';
  const lines = (paths: string[][], color: string) => paths.flatMap((path, pathIndex) => path.slice(1).map((name, i) => {
    const a = pose.points[path[i]], b = pose.points[name];
    return <line key={`${color}-${pathIndex}-${i}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={color} strokeWidth="6" strokeLinecap="round" />;
  }));
  return <section className="demo-card">
    <div className="section-heading"><span className="eyebrow">FOLLOW THE MOVEMENT</span><button className="icon-button" aria-label={play ? 'Pause movement demo' : 'Play movement demo'} aria-pressed={play} onClick={() => setPlay(!play)}>{play ? <Pause size={16} /> : <Play size={16} />}</button></div>
    <svg viewBox="0 0 260 245" role="img" aria-label={`${exercises[exercise].name} illustration. ${rangeText(exercise)}`}>
      <defs><pattern id={gridId} width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#ffffff08" /></pattern></defs>
      <rect width="260" height="245" fill={`url(#${gridId})`} />
      <path d="M25 224H240" stroke="#47615c" />
      {lines(pose.secondary, '#ab9de9')}{lines(pose.paths, '#8ee0c1')}
      {Object.entries(pose.points).filter(([id]) => !id.startsWith('right') && id !== 'neck' && id !== 'centerHip' && !id.toLowerCase().includes('toe')).map(([id, p]) => <circle key={id} cx={p[0]} cy={p[1]} r={id === 'head' ? 12 : 3.5} fill={id === 'head' ? '#8ee0c1' : '#eee8ff'} />)}
      <circle cx={activeJoint[0]} cy={activeJoint[1]} r="10" fill="#c0f4d41a" stroke="#d0f3b5" strokeWidth="1.5" />
      <text x="130" y="240" fill="#d0f3b5" fontSize="11" textAnchor="middle" fontFamily="system-ui, sans-serif">{exercises[exercise].joint} · {degrees}° · {exercise === 'squat' || exercise === 'push_up' || exercise === 'lunge' ? 'SIDE VIEW' : 'FRONT VIEW'}</text>
    </svg>
    <strong>{step}</strong>
    <p>{rangeText(exercise)}</p>
    <small>{exercise === 'push_up' ? 'Keep shoulders, hips and ankles in one straight line. ' : exercise === 'shoulder_press' ? 'Bend at the elbows, then press upwards. ' : exercise === 'lunge' ? 'Step forward, lower, then return upright between reps. ' : ''}One start → target → return cycle counts as one rep. This guide does not measure your movement.</small>
  </section>;
}
