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
  squat: { start: 155, target: 120, description: 'Bend the visible knee to 120° or less, then stand to 155° or more.' },
  lunge: { start: 155, target: 120, description: 'Bend a visible knee to 120° or less, then return upright to 155° or more.' },
  push_up: { start: 150, target: 110, description: 'In a side-on plank, bend the elbow to 110° or less, then extend to 150° or more.' },
  jumping_jack: { start: 35, target: 135, description: 'Raise both arms to 135° or more with feet apart, then lower to 35° or less with feet together.' },
  shoulder_press: { start: 115, target: 155, description: 'Start with elbows bent to 115° or less, extend overhead to 155° or more, then bend again.' },
};
export type PoseMeasurement = {
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
function diagnose(exercise: ExerciseType, image: Joint[], world: Joint[], preferred?: Side): PoseDiagnostics {
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
  const dx = Math.abs(shoulder.x - hip.x), dy = Math.abs(shoulder.y - hip.y);
  let blockedReason: string | null = null;
  if (exercise === 'push_up' && (dx < .06 || dy > dx * 1.15)) blockedReason = 'Get into a plank and turn side-on to the camera. Standing arm bends do not count as push-ups.';
  else if (exercise === 'push_up' && (bodyAngle === null || bodyAngle < 135)) blockedReason = 'Extend your body into a plank so your shoulder, hip and ankle are nearly in line.';
  else if (exercise !== 'push_up' && shoulder.y >= hip.y - .025) blockedReason = 'Keep your torso upright and turn the camera level so your shoulder is above your hip.';
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
  if (countable && exercise === 'push_up' && bodyAngle !== null && bodyAngle < 155) feedback = 'Keep your hips in line with your shoulders and ankles as you move.';
  else if (countable && both && exercise !== 'lunge' && Math.abs(left - right) > 25) feedback = 'Your two sides show different angles. Move slowly; check your position in the preview.';
  const measurement: PoseMeasurement = { left: leftReliable ? left : null, right: rightReliable ? right : null, primary, rest, peak, feedback,
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
  update(exercise: ExerciseType, image: Joint[], world: Joint[], now: number): PoseDiagnostics {
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
    return diagnose(exercise, image, filtered, this.side ?? undefined);
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
  resetPartial() { this.stage = 'waiting'; this.candidate = ''; this.candidateFrames = 0; this.lastSeen = -Infinity; this.sideMask = 3; }
  update(m: { rest: boolean; peak: boolean; countable?: boolean; trackingSide?: Side | 'both' } | null, now: number) {
    if (!Number.isFinite(now)) return false;
    if (now <= this.lastTime) { if (now < this.lastTime) this.resetPartial(); this.lastTime = now; return false; }
    this.lastTime = now;
    if (!m) { if (now - this.lastSeen > 650) this.resetPartial(); this.candidate = ''; this.candidateFrames = 0; return false; }
    if (m.countable === false || m.rest && m.peak) { this.resetPartial(); return false; }
    if (Number.isFinite(this.lastSeen) && now - this.lastSeen > 650) this.resetPartial();
    const mask = m.trackingSide === 'left' ? 1 : m.trackingSide === 'right' ? 2 : 3;
    if (!(this.sideMask & mask)) this.resetPartial();
    this.sideMask &= mask;
    this.lastSeen = now;
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
