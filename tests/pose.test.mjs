import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const code = ts.transpileModule(fs.readFileSync(new URL('../src/pose.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { angle, RepCounter, PoseTracker, measure, movementTargets } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
let passed = 0;
function test(name, fn) { fn(); passed++; console.log('PASS:', name); }
const point = (x, y, z = 0, visibility = .99) => ({ x, y, z, visibility });
const rad = degrees => degrees * Math.PI / 180;
const rotate = (x, y, degrees) => [x * Math.cos(rad(degrees)) - y * Math.sin(rad(degrees)), x * Math.sin(rad(degrees)) + y * Math.cos(rad(degrees))];

// Construct known-angle landmark trajectories; these test the implementation, not camera accuracy.
function pose(type, degrees, { hiddenSide, lowConfidence = false, standingPushup = false, jackFeet = 'auto', asymmetric = false } = {}) {
  const world = Array.from({ length: 33 }, () => point(0, -.6));
  for (const o of [0, 1]) {
    const mirror = o ? -1 : 1;
    let a = asymmetric && o ? 175 : degrees;
    world[11 + o] = point(-.18 * mirror, -.65);
    world[23 + o] = point(-.15 * mirror, -.1);
    world[25 + o] = point(-.15 * mirror, .3);
    world[27 + o] = point((-.15 + .4 * Math.sin(rad(a))) * mirror, .3 - .4 * Math.cos(rad(a)));
    if (type === 'push_up') {
      world[11 + o] = point(-.55, -.15, o * .2);
      world[23 + o] = point(0, -.15, o * .2);
      world[27 + o] = point(.55, -.15, o * .2);
      world[13 + o] = point(-.55, .15, o * .2);
      world[15 + o] = point(-.55 + .3 * Math.sin(rad(a)), .15 - .3 * Math.cos(rad(a)), o * .2);
    } else if (type === 'shoulder_press') {
      const progress = Math.max(0, Math.min(1, (a - 90) / 80));
      world[11 + o] = point(-.18 * mirror, -.4);
      const ex = -.43 + progress * .2, ey = -.3 - progress * .35;
      world[13 + o] = point(ex * mirror, ey);
      const [wx, wy] = rotate(-.18 - ex, -.4 - ey, -a);
      world[15 + o] = point((ex + wx) * mirror, ey + wy);
    } else if (type === 'jumping_jack') {
      const [ux, uy] = rotate(.03, .55, a);
      const scale = .3 / Math.hypot(ux, uy);
      world[13 + o] = point((-.18 + ux * scale) * mirror, -.65 + uy * scale);
      world[15 + o] = point((-.18 + ux * scale * 2) * mirror, -.65 + uy * scale * 2);
      const open = jackFeet === 'open' || jackFeet === 'auto' && a >= 100;
      world[27 + o] = point((open ? -.42 : -.11) * mirror, .7);
    }
  }
  const image = world.map(p => point(.5 + p.x * .36, .53 + p.y * .36));
  if (standingPushup) for (const o of [0, 1]) { image[11 + o] = point(.45 + o * .1, .3); image[23 + o] = point(.45 + o * .1, .55); }
  if (hiddenSide) for (let i = hiddenSide === 'left' ? 11 : 12; i <= 32; i += 2) { image[i].visibility = .1; world[i] = point(NaN, NaN, NaN); }
  if (lowConfidence) for (const p of image) p.visibility = .1;
  return { image, world };
}
function sequence(type, degrees, fps = 20, options = {}) {
  const tracker = new PoseTracker(), counter = new RepCounter(); let now = 0;
  const hold = (degree, ms = 240) => {
    const p = pose(type, degree, options);
    for (let t = 0; t < ms; t += 1000 / fps) { counter.update(tracker.update(type, p.image, p.world, now).measurement, now); now += 1000 / fps; }
  };
  for (const degree of degrees) hold(degree);
  return counter;
}
const rest = { rest: true, peak: false }, peak = { rest: false, peak: true }, moving = { rest: false, peak: false };
function observations(counter, pairs) { for (const [now, m] of pairs) counter.update(m, now); }

test('angle uses all three dimensions and rejects degenerate/nonfinite joints', () => {
  assert.equal(Math.round(angle(point(1, 0), point(0, 0), point(0, 1))), 90);
  assert.equal(Math.round(angle(point(0, 0, 1), point(0, 0), point(0, 0, -1))), 180);
  assert.ok(Number.isNaN(angle(point(0, 0), point(0, 0), point(1, 0))));
  assert.ok(Number.isNaN(angle(point(NaN, 0), point(0, 0), point(1, 0))));
});

for (const type of Object.keys(movementTargets)) {
  const extension = type === 'shoulder_press' || type === 'jumping_jack';
  const base = type === 'jumping_jack' ? 12 : type === 'shoulder_press' ? 90 : 175;
  const target = type === 'jumping_jack' ? 165 : type === 'shoulder_press' ? 175 : 100;
  const middle = (base + target) / 2;
  test(`${type}: five measured full cycles at 5, 10, 20 and 30 fps`, () => {
    for (const fps of [5, 10, 20, 30]) {
      const degrees = [base];
      for (let n = 0; n < 5; n++) degrees.push(base, middle, target, middle, base);
      const c = sequence(type, degrees, fps);
      assert.equal(c.reps, 5, `${type} @ ${fps} fps`);
    }
  });
  test(`${type}: incomplete motion and holding a target never count`, () => {
    assert.equal(sequence(type, [base, middle, base, middle, base]).reps, 0);
    assert.equal(sequence(type, [target, target, target, base]).reps, 0);
    assert.equal(sequence(type, [base, base, middle, target, target, target]).reps, 0);
  });
  test(`${type}: missing/low-confidence landmarks cannot count`, () => {
    const p = pose(type, base, { lowConfidence: true });
    assert.equal(measure(type, p.image, p.world), null);
    assert.equal(measure(type, [], []), null);
    assert.equal(sequence(type, [base, target, base], 20, { lowConfidence: true }).reps, 0);
    const m = measure(type, ...Object.values(pose(type, target)));
    assert.ok(m?.primary >= 0 && m?.primary <= 180);
    assert.ok(Math.abs(m.primary - target) < 1e-6, `${type}: known angle preserved`);
    assert.equal(m.peak, true);
    assert.equal(extension ? m.primary >= movementTargets[type].target : m.primary <= movementTargets[type].target, true);
  });
  if (type !== 'jumping_jack') test(`${type}: visible side counts with the other side hidden and degenerate`, () => {
    for (const hiddenSide of ['left', 'right']) {
      const p = pose(type, base, { hiddenSide });
      const m = measure(type, p.image, p.world);
      assert.ok(m); assert.equal(m[hiddenSide], null); assert.equal(m.rest, true);
      assert.equal(sequence(type, [base, base, middle, target, middle, base, base], 20, { hiddenSide }).reps, 1);
    }
  });
}

test('normal shoulder-press bottom counts while wrists remain above shoulders', () => {
  const p = pose('shoulder_press', 90);
  assert.ok(p.image[15].y < p.image[11].y && p.image[16].y < p.image[12].y);
  assert.equal(measure('shoulder_press', p.image, p.world).rest, true);
  assert.equal(sequence('shoulder_press', [90, 90, 130, 175, 130, 90, 90]).reps, 1);
});
test('standing elbow bends never count as push-ups', () => {
  const p = pose('push_up', 175, { standingPushup: true });
  const m = measure('push_up', p.image, p.world);
  assert.equal(m.countable, false); assert.match(m.feedback, /plank/);
  assert.equal(sequence('push_up', [175, 175, 140, 100, 140, 175, 175], 20, { standingPushup: true }).reps, 0);
});
test('jumping jacks require both visible arms and actual foot opening', () => {
  for (const side of ['left', 'right']) { const p = pose('jumping_jack', 165, { hiddenSide: side }); assert.equal(measure('jumping_jack', p.image, p.world), null); }
  assert.equal(sequence('jumping_jack', [12, 12, 90, 165, 90, 12, 12], 20, { jackFeet: 'closed' }).reps, 0);
  const asymmetric = pose('jumping_jack', 12, { asymmetric: true, jackFeet: 'closed' });
  assert.equal(measure('jumping_jack', asymmetric.image, asymmetric.world).rest, false, 'both arms must return to the start');
});
test('continuous motions count without pausing at the deepest point', () => {
  for (const type of Object.keys(movementTargets)) for (const fps of [5, 10, 20, 30]) {
    const tracker = new PoseTracker(), c = new RepCounter();
    const base = type === 'jumping_jack' ? 12 : type === 'shoulder_press' ? 90 : 175;
    const target = type === 'jumping_jack' ? 165 : type === 'shoulder_press' ? 175 : 100;
    const cycleDuration = 1600;
    for (let now = 0; now <= 5 * cycleDuration + 400; now += 1000 / fps) {
      const t = now < 5 * cycleDuration ? now % cycleDuration / cycleDuration : 0;
      const degree = base + (target - base) * (1 - Math.cos(2 * Math.PI * t)) / 2;
      const p = pose(type, degree);
      c.update(tracker.update(type, p.image, p.world, now).measurement, now);
    }
    assert.equal(c.reps, 5, `${type}: continuous at ${fps} fps`);
  }
});
test('lunge follows the bending leg instead of averaging it with the straight leg', () => {
  const p = pose('lunge', 100, { asymmetric: true });
  assert.ok(Math.abs(measure('lunge', p.image, p.world).primary - 100) < 1e-6);
  assert.equal(sequence('lunge', [175, 175, 140, 100, 140, 175, 175], 20, { asymmetric: true }).reps, 1);
});

test('single-frame false peaks and threshold jitter cannot create repetitions', () => {
  const c = new RepCounter();
  observations(c, [[0, rest], [100, rest], [400, peak], [450, rest], [550, rest], [700, peak], [750, rest], [850, rest]]);
  assert.equal(c.reps, 0);
  assert.equal(sequence('squat', [175, 175, 145, 123, 124, 122, 125, 140, 175, 175]).reps, 0);
});
test('brief occlusion preserves a cycle; prolonged loss cancels it', () => {
  const brief = new RepCounter();
  observations(brief, [[0, rest], [100, rest], [300, peak], [450, null], [600, moving], [750, rest], [850, rest]]);
  assert.equal(brief.reps, 1);
  const long = new RepCounter();
  observations(long, [[0, rest], [100, rest], [300, peak], [500, null], [1000, null], [1100, rest], [1200, rest]]);
  assert.equal(long.reps, 0); assert.equal(long.stage, 'ready');
});
test('side switches cannot join two different limbs into one rep', () => {
  const c = new RepCounter();
  observations(c, [[0, { ...rest, trackingSide: 'left' }], [100, { ...rest, trackingSide: 'left' }], [300, { ...peak, trackingSide: 'left' }], [600, { ...rest, trackingSide: 'right' }], [700, { ...rest, trackingSide: 'right' }]]);
  assert.equal(c.reps, 0); assert.equal(c.stage, 'ready');
});
test('PoseTracker locks a side despite confidence fluctuations and explains missing joints', () => {
  const t = new PoseTracker();
  const first = pose('squat', 175); first.image[12].visibility = .7;
  assert.equal(t.update('squat', first.image, first.world, 0).measurement.trackingSide, 'left');
  const changed = pose('squat', 140); changed.image[11].visibility = .6;
  assert.equal(t.update('squat', changed.image, changed.world, 100).measurement.trackingSide, 'left');
  changed.image[27].visibility = .1;
  const missing = t.update('squat', changed.image, changed.world, 200);
  assert.equal(missing.measurement, null); assert.ok(missing.missingJoints.includes('left ankle'));
  t.update('squat', changed.image, changed.world, 500);
  assert.equal(t.update('squat', changed.image, changed.world, 850).measurement.trackingSide, 'right');
});
test('reset, non-monotonic timestamps, duplicate frames and posture blocks never complete a partial rep', () => {
  for (const problem of ['reset', 'backwards', 'blocked']) {
    const c = new RepCounter(); observations(c, [[0, rest], [100, rest], [300, peak]]);
    if (problem === 'reset') c.resetPartial();
    if (problem === 'backwards') c.update(peak, 200);
    if (problem === 'blocked') c.update({ ...peak, countable: false }, 400);
    observations(c, [[600, rest], [700, rest]]); assert.equal(c.reps, 0);
  }
  const c = new RepCounter(); c.update(rest, 0); for (let i = 0; i < 20; i++) c.update(rest, 0); assert.equal(c.stage, 'waiting');
});
console.log(`\n${passed} pose-engine checks passed. Generated landmark fixtures are not evidence of real-camera recognition accuracy.`);
