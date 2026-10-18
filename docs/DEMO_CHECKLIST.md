# Demonstration checklist

## Before presenting

Install Python requirements using the interpreter you will launch. The archive includes the model checkpoint and a built frontend. Start the server, open the local app, and check Preferences: MotionBERT must say Ready. The live camera model is bundled too. Verify camera access in the presentation browser before the demo.

## Suggested 5-minute walkthrough

1. Overview: explain the empty initial history and genuine session totals.
2. Preferences: enter your name and choose a small target, such as 3 reps.
3. Exercise Library: open a movement guide and explain the counting thresholds and camera placement.
4. Movement Studio: allow the camera, stand fully in view, and hold the starting position. Show the skeleton overlay and measured angles.
5. Complete controlled repetitions. Show that incomplete movement and obscured joints do not automatically count. Demonstrate pause/resume.
6. Finish and save. The session report shows the recorded camera measurements.
7. Click Analyze with MotionBERT. Explain the 33-to-17 joint mapping, 2D/confidence input and actual DSTformer inference.
8. Rotate the 3D skeleton, scrub the timeline, slow playback and inspect the angle chart and ROM.
9. Export JSON or print/PDF. Open Session History and Progress to show the persisted session and genuine totals.
10. Reload the app to demonstrate SQLite persistence.

## If live capture is unsuitable

Use a previously exported real MotionAI recording and import it through Session History. Keep its source labeled Imported recording. Do not present generated test fixtures or synthetic training data as human camera performance.

## Likely viva questions

Why both MediaPipe and MotionBERT? MediaPipe supplies live camera joints; MotionBERT analyzes their temporal 2D sequence to estimate 3D pose.

Why manual exercise selection? The supplied pose checkpoint is not trained for these five exercise labels. Manual selection gives honest, deterministic exercise-specific rules.

How are reps counted? A stable starting position, target-range position and return are required. Hysteresis, timing constraints and tracking-loss reset reduce false counts.

How is form evaluated? Live evidence-based heuristic cues use measured angles and side differences. No validated correct/incorrect classifier is claimed.

What is stored? Camera landmark coordinates, timestamps, metadata, preferences and actual model results in SQLite. Video is not stored or uploaded.

What remains to improve? Real exercise dataset evaluation, a validated exercise/form classifier, calibrated scale, per-person threshold adaptation, better occlusion handling and multi-user deployment.
