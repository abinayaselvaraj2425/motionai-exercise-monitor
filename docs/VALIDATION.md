# Validation record

Verified in the local Windows environment, September 16, 2026.

## Passed checks

- TypeScript compilation checks (`npm run lint`).
- Production frontend build (`npm run build`).
- Focused pose logic: 3D angle calculations, complete cycles, jitter rejection, tracking-loss reset and confidence gating for all five exercise selections.
- Official MotionBERT-Lite checkpoint loads with strict key/shape matching: 16,001,549 parameters.
- Python API tests: checkpoint/hash validation; H36M channel and aspect-ratio adapter; profile persistence and validation; origin protection; invalid recording rejection; session create/open/analyze/cache/delete.
- Real MotionBERT inference on explicitly generated test fixtures returns finite [T,17,3] pose coordinates and angle trajectories.
- Browser walkthrough: overview, library, studio, model status, saved report, actual inference button and interactive 3D replay. Camera initialization, pause and empty-capture handling were exercised.
- Package dependency audit: no vulnerabilities reported for the installed lockfile during this run.

## Important interpretation

Generated fixtures are isolated tests, not exercise dataset evaluation or human-motion accuracy evidence. They are not seeded into submission history. The live browser test confirmed tracker initialization and overlay operation; it did not establish rep-count or form-assessment accuracy on a labeled exercise dataset.

No recognition percentage, form-classification accuracy, medical validation, measured sEMG, calorie estimate or clinical claim is included. MotionBERT is used for real 3D pose lifting. Camera viewpoint, lighting, occlusion, virtual-joint mapping and tracking gaps remain limitations.

## Dark studio revision and supplied dataset
TypeScript checks and production build pass. Rep tests include five measured squat cycles with far-side occlusion, full-cycle gating, jitter rejection, brief occlusion grace and prolonged loss reset. Seven Python tests pass with ResourceWarning treated as errors, including strict official checkpoint loading and actual dataset inference.

All 2,589 paired clips audited: 2,588 support finite image projection input. RawData/101_18_0_6_1_chair.txt contains an infinite image coordinate; its original 3D skeleton is retained and replayable, with an explicit warning and MotionBERT disabled. Archive MD5 matches Zenodo. No research labels were changed, no training or accuracy experiment was fabricated. Personal camera accuracy still requires trials on real user repetitions.
