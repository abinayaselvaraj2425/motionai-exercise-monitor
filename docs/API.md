# API contract

Base URL: http://localhost:3000. Interactive OpenAPI documentation: /docs.

| Endpoint | Purpose |
|---|---|
| GET /api/health | Actual model load status, parameter count and checkpoint hash |
| GET /api/profile | Saved local profile or defaults |
| PUT /api/profile | Validate and save name, weeklyGoal, repTarget and audio |
| GET /api/sessions | Summary list ordered by date |
| POST /api/sessions | Validate and save a camera or imported recording (201) |
| GET /api/sessions/{id} | Full recording and any saved model result |
| POST /api/sessions/{id}/analyze | Real MotionBERT inference; cached after completion |
| DELETE /api/sessions/{id} | Remove that session |

Session creation accepts exercise, date (ISO timestamp with timezone), reps, duration in seconds, target, source and frames. Exercise is one of squat, lunge, push_up, jumping_jack, shoulder_press. Source is camera or import. Each frame has strictly increasing timestamp in milliseconds, video width/height, 33 image landmarks, 33 world landmarks and measured live metrics. Landmark coordinates must be finite numbers; visibility must lie in [0,1]. At least 2 and at most 3,600 frames are accepted. Reps and target are integers; target lies in [1,100]. Maximum upload size is 30 MB.

The server generates id and resets motionbert to null on creation, even if an uploaded file includes results. Completed analysis contains model/checkpoint provenance, measured latency, parameter count, input shape, window count, 3D frames, angle trajectories, ROM statistics and mapping notes.

Failures use JSON `detail`: 422 validation, 404 missing session, 503 unavailable model and 500 inference error. Writes from a different browser origin are rejected. The local workspace has no account-authentication layer.

## Research data
GET /api/dataset: verified archive catalogue and label counts. GET /api/dataset/{filename}: original 25-joint replay with timestamps and tracking fraction. POST /api/dataset/{filename}/analyze: actual MotionBERT predictions from paired raw image projections. Catalogue filenames are the allowlist; arbitrary filesystem paths are rejected. Research recordings never populate personal workout history.
