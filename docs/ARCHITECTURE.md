# Architecture

```
Browser camera -> MediaPipe Pose Landmarker -> 33 image/world joints
  |-> confidence & framing gate -> exercise rules -> live cues and rep FSM
  |-> timestamped recording -> FastAPI -> SQLite session
                                 |-> H36M-style adapter (17 joints)
                                 |-> normalized 2D x/y + visibility
                                 |-> MotionBERT-Lite / DSTformer
                                 |-> root-relative 3D predictions
                                 |-> joint angles and range of motion
                                 |-> stored results -> React reports / Three.js replay
```

## Frontend

React 19 and TypeScript. `src/App.tsx` supplies eight application screens. `src/pose.ts` implements measured-angle feedback and the repetition state machine. `LiveCameraTracker.tsx` owns camera and pose-estimator lifecycle. `SkeletonViewer.tsx` reuses geometry and supports touch/mouse orbit, timeline, play/pause and speed changes. Native CSS provides responsive layouts and print styling. `src/data.ts` defines the API contracts.

## Backend

`backend/submission_api.py` serves the built app, profiles, sessions, validation and model inference. SQLite stores a session ID/date plus JSON payload and profile settings. Database contexts commit or roll back and always close connections. Writes use bound SQL parameters. Inference is serialized to avoid concurrent large model requests. Repeated analysis returns the stored result.

## MotionBERT

`backend/motionbert/model.py` contains the DSTformer architecture. The fine-tuned Lite configuration uses dim_feat=256, dim_rep=512, depth=5, num_heads=8, maxlen=243, 17 joints and LayerNorm epsilon 1e-6. Exactly 16,001,549 parameters load from the official checkpoint. All keys/shapes must match (`strict=True`). The backend uses eval mode and torch.inference_mode; CPU inference is supported.

## Measured quantities

Live and report joint angles use the angle between two bone vectors. ROM is maximum minus minimum over recorded valid poses. Mean side difference is the mean absolute angle difference, not a quality score. Time is derived from monotonic recording timestamps; saved dates use UTC. Session duration includes pauses. MotionBERT output has no calibrated metric scale, so metric displacement, velocity and physiological measurements are not presented.

## Storage and local operation

Profile changes and saved recordings persist in SQLite across restart. History contains no seeded examples. Import validates JSON structure, finite values, joint counts, timestamps, dimensions, angles and metadata. Imported model outputs are discarded; analysis must run on the server. The server is intended for a single local user and is bound to loopback. Authentication and multi-user deployment are future extensions.
