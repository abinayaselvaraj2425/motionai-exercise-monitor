# Verification: original-design deployment release

## Latest release checks

- Original six source stylesheets and HTML restored from MotionAI-redesigned (2).zip; no Studio stylesheet is loaded. Original Home markup is rendered by HomeDashboard.
- Ten new regression checks pass: cross-site writes, actual chat upload size, private anonymous responses, account throttling across IPs, conversation budget, provider-field filtering/consent, follow-ups after long replies, busy inference retry, gap coverage and low-rate coverage.
- Existing frontend and backend suites below were rerun successfully. Google/OpenAI remain mocked; MotionBERT inference uses the real verified checkpoint.
- A GitHub workflow now runs full HTTP suites and Docker build/startup on an unrestricted Linux runner after upload. The workflow itself has not been run here.

## Passed

- TypeScript check and production frontend build.
- 35 pose-engine checks: known 3D angles, 5–30 fps cycles, personal starts, reduced ranges, short/slow continuous movement, jitter rejection, missing joints, side continuity, exercise-position gates and sustained coaching.
- 9 camera lifecycle/recovery checks, 7 calendar/progress checks and 6 routine-camera checks.
- 7 React rendering checks: login, onboarding, progress, routine report, help, coaching compatibility and the actual Home component with empty/personalised states.
- 6 coordinate-based report/coaching checks, including short sets, limited tracking, sustained vs single-frame cues and wrong movements.
- 9 direct backend checks: account isolation, identity middleware, recovery/deletion, validated import/export, routine links, comparisons/trends, posture gates and real MotionBERT inference.
- 7 local-launcher checks.
- 11 deployment/provider checks: HTTPS configuration, Render/local callbacks, origins, cookies, browser security headers, profile-photo/widget rejection, built-in help without network, mocked Google PKCE/state round trip, mocked OpenAI schema and safe provider errors.
- YAML parsing for Compose/Render, Python module parsing and camera-asset SHA-256 verification.
- Strict MotionBERT loading and real CPU inference: 16,001,549 parameters; checkpoint SHA-256 9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f. Reports use the resulting 17-joint sequences.

## Still to test outside this environment

- Local socket creation is blocked here. Full HTTP integration and a live browser/webcam walkthrough could not run.
- Screen rendering is not screenshot or mobile-layout verification. No real person was recorded during these checks.
- Docker is unavailable. Container files were reviewed for paths and configuration, but an image build, hosted deployment, persistent-storage restart and load test remain pending.
- Google/OpenAI connections were mocked, not tested with live credentials. Configure and test your providers before treating them as live.
- Synthetic movement tests do not establish clinical validity or recognition accuracy across all people.

## Repeat locally

```text
npm run lint
npm test
npm run test:ui
python -m unittest tests.test_coaching tests.test_deployment tests.test_direct tests.test_launch -v
npm run build
```

Run npm test before coaching tests: it creates the shared landmark fixtures. On an unrestricted machine, also run the HTTP integration suites in tests.test_platform, tests.test_api and tests.test_routines, then complete the walkthrough in DEPLOYMENT.md.

Older screenshots and validation documents describe historical versions, not Studio.
