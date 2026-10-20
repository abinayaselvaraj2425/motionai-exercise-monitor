export type ExerciseType = 'squat' | 'lunge' | 'push_up' | 'jumping_jack' | 'shoulder_press';
export type Joint = { x: number; y: number; z: number; visibility?: number };
type Side = 'left' | 'right';
export const exercises = {
  squat: { name: 'Bodyweight squat', cue: 'Turn sideways or slightly towards the camera. Show one complete shoulder, hip, knee and ankle.', joint: 'Knee' },
  lunge: { name: 'Forward lunge', cue: 'Use a side or three-quarter view. Keep the bending leg visible and return upright between reps.', joint: 'Knee' },
  push_up: { name: 'Push-up', cue: 'Place the camera beside you at floor level. Show a shoulder, elbow, wrist, hip and ankle.', joint: 'Elbow' },
  jumping_jack: { name: 'Jumping jack', cue: 'Face the camera. Show both arms and ankles, with space above your head and beside your feet.', joint: 'Shoulder' },
  shoulder_press: { name: 'Shoulder press', cue: 'Stand or sit upright. Show a shoulder, elbow, wrist and hip, including your hand overhead.', joint: 'Elbow' },
};
// Explicit demonstration thresholds, not a clinical assessment of safe range.
export const movementTargets: Record<ExerciseType, { start: number; target: number; description: string }> = {
  squat: { start: 145, target: 125, description: 'Lower your hips through a comfortable, clear bend, then return upright.' },
  lunge: { start: 145, target: 125, description: 'Step into a split stance, lower with control, then return upright.' },
  push_up: { start: 140, target: 115, description: 'From a plank, lower your chest and press back to your starting position.' },
  jumping_jack: { start: 45, target: 120, description: 'Open your arms and feet together, then bring them back to the start.' },
  shoulder_press: { start: 125, target: 145, description: 'Start with bent elbows, press your hands overhead, then lower them again.' },
};
export type PoseMeasurement = {
  exercise?: ExerciseType; gestureReady?: boolean; cycleClosed?: boolean; coaching?: string;
  left: number | null; right: number | null; primary: number;
  rest: boolean; peak: boolean; feedback: string; visible: number; bodyAngle: number | null;
  leftReliable: boolean; rightReliable: boolean; trackingSide: Side | 'both';
  confidence: number; countable: boolean; blockedReason: string | null;
  progress: number; targetLabel: string;
};
export type PoseDiagnostics = {
  measurement: PoseMeasurement | null; message: string; missingJoints: string[];
  tracking: 'none' | 'partial' | 'ready' | 'position';
};
const names: Record<number, string> = { 11: 'left shoulder', 12: 'right shoulder', 13: 'left elbow', 14: 'right elbow', 15: 'left wrist', 16: 'right wrist', 23: 'left hip', 24: 'right hip', 25: 'left knee', 26: 'right knee', 27: 'left ankle', 28: 'right ankle' };
const clamp = (n: number, low = 0, high = 1) => Math.max(low, Math.min(high, n));
const finite = (p: Joint | undefined): p is Joint => !!p && Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z);
const visible = (image: Joint[], i: number) => finite(image[i]) && (image[i].visibility ?? 0) >= .45 && image[i].x >= -.025 && image[i].x <= 1.025 && image[i].y >= -.025 && image[i].y <= 1.025;
const requiredLeft = (exercise: ExerciseType) => exercise === 'push_up' ? [11, 13, 15, 23, 27] : exercise === 'shoulder_press' ? [11, 13, 15, 23] : exercise === 'jumping_jack' ? [11, 13, 15, 23, 27] : [11, 23, 25, 27];
const idsFor = (exercise: ExerciseType, side: Side) => requiredLeft(exercise).map(i => i + (side === 'right' ? 1 : 0));
const sideScore = (exercise: ExerciseType, image: Joint[], world: Joint[], side: Side) => {
  const ids = idsFor(exercise, side);
  return ids.every(i => visible(image, i) && finite(world[i])) && Number.isFinite(jointAngle(exercise, world, side)) ? Math.min(...ids.map(i => image[i].visibility ?? 0)) : 0;
};

export function angle(a: Joint, b: Joint, c: Joint) {
  if (!finite(a) || !finite(b) || !finite(c)) return NaN;
  const u = [a.x - b.x, a.y - b.y, a.z - b.z], v = [c.x - b.x, c.y - b.y, c.z - b.z];
  const norm = Math.hypot(...u) * Math.hypot(...v);
  return norm < 1e-8 ? NaN : Math.acos(clamp(u.reduce((sum, n, i) => sum + n * v[i], 0) / norm, -1, 1)) * 180 / Math.PI;
}
function jointAngle(exercise: ExerciseType, p: Joint[], side: Side) {
  const o = side === 'right' ? 1 : 0;
  return exercise === 'jumping_jack' ? angle(p[23 + o], p[11 + o], p[13 + o])
    : exercise === 'push_up' || exercise === 'shoulder_press' ? angle(p[11 + o], p[13 + o], p[15 + o])
      : angle(p[23 + o], p[25 + o], p[27 + o]);
}
function diagnose(exercise: ExerciseType, image: Joint[], world: Joint[], preferred?: Side, aspect = 1): PoseDiagnostics {
  if (!image.length || !world.length) return { measurement: null, message: 'No person detected. Step into view and make sure the room is well lit.', missingJoints: requiredLeft(exercise).map(i => names[i]), tracking: 'none' };
  let leftScore = sideScore(exercise, image, world, 'left'), rightScore = sideScore(exercise, image, world, 'right');
  const left = leftScore ? jointAngle(exercise, world, 'left') : NaN;
  const right = rightScore ? jointAngle(exercise, world, 'right') : NaN;
  if (!Number.isFinite(left)) leftScore = 0;
  if (!Number.isFinite(right)) rightScore = 0;
  const leftReliable = leftScore > 0, rightReliable = rightScore > 0;
  const missing = (side: Side) => idsFor(exercise, side).filter(i => !visible(image, i) || !finite(world[i])).map(i => names[i]);
  if ((!leftReliable && !rightReliable) || (exercise === 'jumping_jack' && (!leftReliable || !rightReliable))) {
    const leftMissing = missing('left'), rightMissing = missing('right');
    const missingJoints = exercise === 'jumping_jack' ? [...leftMissing, ...rightMissing] : leftMissing.length <= rightMissing.length ? leftMissing : rightMissing;
    return { measurement: null, message: missingJoints.length ? `Show your ${missingJoints.join(', ')}. ${exercises[exercise].cue}` : 'Joint positions are not clear yet. Hold still briefly and improve the lighting.', missingJoints, tracking: 'partial' };
  }
  const side: Side = preferred === 'left' && leftReliable ? 'left' : preferred === 'right' && rightReliable ? 'right' : leftScore >= rightScore ? 'left' : 'right';
  const both = leftReliable && rightReliable;
  const trackingSide = (exercise === 'jumping_jack' || exercise === 'lunge' && both) ? 'both' : side;
  const primary = exercise === 'jumping_jack' ? Math.min(left, right) : exercise === 'lunge' && both ? Math.min(left, right) : side === 'left' ? left : right;
  const o = side === 'right' ? 1 : 0;
  const shoulder = image[11 + o], hip = image[23 + o], wrist = image[15 + o];
  const ownOverhead = (s: Side) => image[s === 'left' ? 15 : 16].y < image[s === 'left' ? 11 : 12].y - .015;
  const body = visible(image, 27 + o) && finite(world[27 + o]) ? angle(world[11 + o], world[23 + o], world[27 + o]) : NaN;
  const bodyAngle = Number.isFinite(body) ? body : null;
  const dx = Math.abs(shoulder.x - hip.x) * aspect, dy = Math.abs(shoulder.y - hip.y);
  let blockedReason: string | null = null;
  if (exercise === 'push_up' && (dx < .06 || dy > dx * 1.15)) blockedReason = 'Get into a plank and turn side-on to the camera. Standing arm bends do not count as push-ups.';
  else if (exercise === 'push_up' && (bodyAngle === null || bodyAngle < 105)) blockedReason = 'Show your full plank from the side so your shoulders, hips and ankles can be followed.';
  else if (exercise !== 'push_up' && shoulder.y >= hip.y - .015) blockedReason = 'Keep your torso upright and turn the camera level so your shoulder is above your hip.';
  const targets = movementTargets[exercise];
  const extension = exercise === 'shoulder_press' || exercise === 'jumping_jack';
  // Half a degree also keeps endpoint decisions consistent with the rounded angle shown in the UI.
  let rest = extension ? primary <= targets.start + .5 : primary >= targets.start - .5;
  let peak = extension ? primary >= targets.target - .5 : primary <= targets.target + .5;
  if (exercise === 'shoulder_press') peak = peak && !!wrist && ownOverhead(side);
  if (exercise === 'jumping_jack') {
    // A narrow hip estimate must not make closed feet appear open.
    const hipWidth = Math.abs(image[23].x - image[24].x);
    const shoulderWidth = Math.abs(image[11].x - image[12].x);
    const scale = Math.max(.04, hipWidth, shoulderWidth * .75);
    const ankleWidth = Math.abs(image[27].x - image[28].x);
    rest = Math.max(left, right) <= targets.start + .5 && ankleWidth <= scale * 1.55;
    peak = peak && ownOverhead('left') && ownOverhead('right') && ankleWidth >= scale * 1.8;
  }
  const countable = blockedReason === null;
  if (!countable) { rest = false; peak = false; }
  let feedback = blockedReason ?? (peak ? 'Target reached. Return to the starting position to complete one rep.' : rest ? 'Starting position found. Follow the demo, then return here.' : targets.description);
  let coaching = '';
  if (countable && exercise === 'push_up' && bodyAngle !== null && bodyAngle < 155) coaching = 'Move your hips and shoulders together. Try to keep your body in one long line.';
  else if (countable && both && exercise !== 'lunge' && Math.abs(left - right) > 25) feedback = 'Your two sides show different angles. Move slowly; check your position in the preview.';
  if (countable && both && exercise !== 'lunge' && Math.abs(left - right) > 25 && !coaching) coaching = 'Try moving both sides together. Check that both sides are equally visible to the camera.';
  if (countable && exercise === 'shoulder_press' && wrist && Math.abs(wrist.x-image[13+o].x)*aspect>Math.abs(wrist.y-image[13+o].y)*.7) coaching='Bring your wrists more directly above your elbows as you press. Use a comfortable height.';
  if(countable && (exercise==='squat'||exercise==='lunge') && dx>dy*.9) coaching='Try keeping your chest a little more lifted as you lower. Use a smaller comfortable bend if that helps.';
  let gestureReady=true;
  let cycleClosed=rest;
  if(exercise==='shoulder_press') {
    gestureReady=wrist.y<image[13+o].y && wrist.y<shoulder.y+.03 && angle(world[23+o],world[11+o],world[13+o])>55;
    if(countable && !gestureReady && primary>135 && !coaching) coaching='Send your hands upward beside your head, rather than forward. Keep the movement comfortable.';
  }
  if(exercise==='jumping_jack') {
    const scale=Math.max(.04,Math.abs(image[23].x-image[24].x),Math.abs(image[11].x-image[12].x)*.75);
    const feet=Math.abs(image[27].x-image[28].x);
    gestureReady=Math.min(left,right)>65 && feet>=scale*1.55;
    cycleClosed=Math.max(left,right)<65 && feet<=scale*1.55;
    if(countable && Math.min(left,right)>65 && !gestureReady) coaching='Open your feet as your arms rise, then bring both back together. A smaller step is okay.';
  }
  if(exercise==='lunge' && visible(image,27) && visible(image,28)) {
    const feet=Math.hypot(world[27].x-world[28].x,world[27].z-world[28].z);
    const leg=Math.hypot(world[23+o].x-world[27+o].x,world[23+o].y-world[27+o].y,world[23+o].z-world[27+o].z);
    gestureReady=feet>leg*.3;
    if(countable&&!gestureReady) coaching='Place one foot ahead of the other, then lower and rise in that split stance.';
  }
  const measurement: PoseMeasurement = { exercise, gestureReady, cycleClosed, coaching, left: leftReliable ? left : null, right: rightReliable ? right : null, primary, rest, peak, feedback,
    visible: [...requiredLeft(exercise), ...requiredLeft(exercise).map(i => i + 1)].filter(i => visible(image, i)).length,
    bodyAngle, leftReliable, rightReliable, trackingSide, confidence: trackingSide === 'both' ? Math.min(leftScore, rightScore) : side === 'left' ? leftScore : rightScore,
    countable, blockedReason, progress: clamp(extension ? (primary - targets.start) / (targets.target - targets.start) : (targets.start - primary) / (targets.start - targets.target)), targetLabel: targets.description };
  return { measurement, message: feedback, missingJoints: [], tracking: countable ? 'ready' : 'position' };
}
export function measure(exercise: ExerciseType, image: Joint[], world: Joint[]): PoseMeasurement | null {
  return diagnose(exercise, image, world).measurement;
}

/** Smooth actual 3D joint coordinates and keep the selected body side stable across frames. */
export class PoseTracker {
  private exercise: ExerciseType | null = null;
  private side: Side | null = null;
  private missingSince: number | null = null;
  private lastTime = -Infinity;
  private smoothed: Joint[] = [];
  reset() { this.exercise = null; this.side = null; this.missingSince = null; this.lastTime = -Infinity; this.smoothed = []; }
  update(exercise: ExerciseType, image: Joint[], world: Joint[], now: number, aspect = 1): PoseDiagnostics {
    if (this.exercise !== exercise || !Number.isFinite(now) || now <= this.lastTime || now - this.lastTime > 650) this.reset();
    this.exercise = exercise;
    const delta = Number.isFinite(this.lastTime) ? now - this.lastTime : 1000;
    this.lastTime = now;
    const left = sideScore(exercise, image, world, 'left'), right = sideScore(exercise, image, world, 'right');
    if (exercise !== 'jumping_jack' && exercise !== 'lunge') {
      if (!this.side && (left || right)) this.side = left >= right ? 'left' : 'right';
      if (this.side && !(this.side === 'left' ? left : right)) {
        this.missingSince ??= now;
        if (now - this.missingSince < 600) return { measurement: null, message: `Keep your ${this.side} side in view. Counting pauses briefly when a joint is hidden.`, missingJoints: idsFor(exercise, this.side).filter(i => !visible(image, i) || !finite(world[i])).map(i => names[i]), tracking: image.length ? 'partial' : 'none' };
        this.side = left ? 'left' : right ? 'right' : null;
        this.smoothed = [];
      } else this.missingSince = null;
    }
    // A time based filter behaves consistently at 10, 20 and 30 frames per second.
    const alpha = 1 - Math.exp(-Math.min(delta, 250) / 45);
    const filtered = world.map((p, i) => {
      const old = this.smoothed[i];
      if (!visible(image, i) || !finite(p)) return p;
      return finite(old) ? { ...p, x: old.x + alpha * (p.x - old.x), y: old.y + alpha * (p.y - old.y), z: old.z + alpha * (p.z - old.z) } : { ...p };
    });
    this.smoothed = filtered;
    return diagnose(exercise, image, filtered, this.side ?? undefined, aspect);
  }
}

/** A complete start → target → start cycle, with timing and tracking continuity checks. */
export class RepCounter {
  reps = 0;
  stage: 'waiting' | 'ready' | 'target' = 'waiting';
  candidate = '';
  since = 0;
  started = 0;
  lastRep = -Infinity;
  lastSeen = -Infinity;
  private lastTime = -Infinity;
  private readyAt = 0;
  private candidateFrames = 0;
  private sideMask = 3;
  private baseline: number | null = null;
  private peakAt = 0;
  private adaptiveExercise: ExerciseType | null = null;
  private extreme = 0;
  private learnedRange: number | null = null;
  private startSamples: {time:number;value:number}[] = [];
  private gestureSeen = false;
  resetPartial() { this.stage = 'waiting'; this.candidate = ''; this.candidateFrames = 0; this.lastSeen = -Infinity; this.sideMask = 3; this.baseline=null;this.peakAt=0;this.startSamples=[];this.gestureSeen=false;this.learnedRange=null; }
  get instruction() { return this.stage==='waiting'?'Let me find your starting position. Move at your own pace.':this.stage==='target'?'Movement recognised. Come back towards where you started.':'Ready. Move through a comfortable bend and return.'; }
  update(m: { rest: boolean; peak: boolean; countable?: boolean; trackingSide?: Side | 'both'; exercise?:ExerciseType;primary?:number;gestureReady?:boolean;cycleClosed?:boolean } | null, now: number) {
    if (!Number.isFinite(now)) return false;
    if (now <= this.lastTime) { if (now < this.lastTime) this.resetPartial(); this.lastTime = now; return false; }
    const frameInterval=now-this.lastTime;
    this.lastTime = now;
    if (!m) { if (now - this.lastSeen > 650) this.resetPartial(); this.candidate = ''; this.candidateFrames = 0; return false; }
    if (m.countable === false || m.rest && m.peak) { this.resetPartial(); return false; }
    if (Number.isFinite(this.lastSeen) && now - this.lastSeen > 650) this.resetPartial();
    const mask = m.trackingSide === 'left' ? 1 : m.trackingSide === 'right' ? 2 : 3;
    if (!(this.sideMask & mask)) this.resetPartial();
    this.sideMask &= mask;
    this.lastSeen = now;
    if(m.exercise && Number.isFinite(m.primary)) {
      if(this.adaptiveExercise!==m.exercise){this.resetPartial();this.adaptiveExercise=m.exercise;this.lastSeen=now;this.sideMask=mask;}
      const v=m.primary!,up=m.exercise==='shoulder_press'||m.exercise==='jumping_jack';
      // Broad exercise-specific orientation, then a personal starting angle.
      // No fixed "perfect" endpoint and no requirement to hold at the peak.
      const startPose=up?v<=(m.exercise==='jumping_jack'?65:155):v>=110;
      if(this.stage==='waiting') {
        if(startPose){
          this.startSamples.push({time:now,value:v});this.startSamples=this.startSamples.filter(s=>now-s.time<=350);
          if(this.startSamples.length>=2 && now-this.startSamples[0].time>=100 && Math.max(...this.startSamples.map(s=>s.value))-Math.min(...this.startSamples.map(s=>s.value))<28){this.baseline=up?Math.min(...this.startSamples.map(s=>s.value)):Math.max(...this.startSamples.map(s=>s.value));this.extreme=this.baseline;this.stage='ready';this.readyAt=this.startSamples[0].time;}
        } else this.startSamples=[];
        return false;
      }
      if(this.baseline===null){this.resetPartial();return false;}
      if(this.stage==='ready' && (up?v<this.baseline:v>this.baseline)){this.baseline=v;this.extreme=v;}
      const excursion=up?v-this.baseline:this.baseline-v;
      this.extreme=up?Math.max(this.extreme,v):Math.min(this.extreme,v);
      const floor=m.exercise==='jumping_jack'?45:m.exercise==='push_up'||m.exercise==='shoulder_press'?20:18;
      const threshold=this.learnedRange===null?floor:Math.max(floor,Math.min(floor+12,this.learnedRange*.5));
      if(excursion>=threshold && m.gestureReady!==false)this.gestureSeen=true;
      if(this.stage==='ready') {
        const enough=excursion>=threshold;
        if(enough){if(!this.peakAt)this.peakAt=now;else if(now-this.peakAt>=70&&now-this.readyAt>=150){this.stage='target';this.started=now;this.candidate='';}}
        else this.peakAt=0;
      } else if(excursion<=Math.max(7,Math.min(16,Math.abs(this.extreme-this.baseline)*.35)) && this.gestureSeen && (m.exercise!=='jumping_jack'||(m.cycleClosed??m.rest))) {
        if(this.candidate!=='return'){this.candidate='return';this.since=now;}
        if((now-this.since>=50||frameInterval>=120)&&now-this.started>=100&&now-this.readyAt>=450&&now-this.lastRep>=450){
          const range=Math.abs(this.extreme-this.baseline);this.learnedRange=this.learnedRange===null?range:this.learnedRange*.7+range*.3;
          this.reps++;this.lastRep=now;this.stage='ready';this.readyAt=now;this.baseline=v;this.extreme=v;this.gestureSeen=false;this.peakAt=0;this.candidate='';return true;
        }
      } else this.candidate='';
      if(now-this.readyAt>30000)this.resetPartial();
      return false;
    }
    const state = m.rest ? 'rest' : m.peak ? 'peak' : 'moving';
    if (this.candidate !== state) { this.candidate = state; this.since = now; this.candidateFrames = 1; } else this.candidateFrames++;
    const stableRest = m.rest && this.candidateFrames >= 2 && now - this.since >= 50;
    if (this.stage === 'waiting' && stableRest) { this.stage = 'ready'; this.readyAt = now; }
    else if (this.stage === 'ready' && m.peak && now - this.readyAt >= 160) { this.stage = 'target'; this.started = now; }
    else if (this.stage === 'target' && m.rest) {
      // A one-frame angle spike followed immediately by the start pose is not a rep.
      if (now - this.started < 160) { this.stage = 'ready'; this.readyAt = now; }
      else if (stableRest && now - this.readyAt >= 400 && now - this.lastRep >= 500) {
        this.reps++; this.lastRep = now; this.stage = 'ready'; this.readyAt = now; this.sideMask = mask; return true;
      }
    }
    return false;
  }
}

/** Debounce technique cues so a single noisy frame does not become advice. */
export class LiveCoach {
  private candidate='';private since=0;private shown='';private last=-Infinity;
  reset(){this.candidate='';this.shown='';this.last=-Infinity;}
  update(m:PoseMeasurement|null,now:number){
    if(now<=this.last||now-this.last>650)this.reset();this.last=now;
    const next=m?.countable?m.coaching||'':'';
    if(next!==this.candidate){this.candidate=next;this.since=now;}
    if(now-this.since>=(next?300:650))this.shown=next;
    if(!m||!m.countable)this.shown='';
    return this.shown;
  }
}
