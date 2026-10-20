# MotionAI workspace update

## Application flow

Register with a username/password → save the recovery code → sign in → optional personal setup → Home.
Google sign-in uses an authorization-code flow with state, nonce and PKCE when the installation has credentials.
Home opens either a single exercise or a routine. The sidebar begins Overview, Progress, History, Session reports.

The studio checks the camera and model, gives a three-second countdown, and records joint trajectories.
Users can pause, resume, finish a partial set, or recover an interrupted recording in the same account/browser.
Routines preserve completed and partial steps, offer guided timers, rest extension and skipping, and link each recording to its own report.

## Analysis method

- Live counting uses a visible starting position and a sustained, meaningful excursion and return; endpoints adapt to the starting angle. It retains minimum movement and timing checks, exercise posture gates, tracking continuity and side stability. These are engineering heuristics, not medical thresholds.
- Squats/lunges examine knee angles; push-ups/presses examine elbow angles; jumping jacks examine shoulder elevation with feet opening. Press recognition also requires overhead movement; push-ups require a plank; lunges use a split-stance gate when both feet are visible.
- Form cues and counting are separate. An imperfect but recognisable cycle can count.
- Reports recompute angles from joint coordinates instead of trusting uploaded metrics. They describe typical excursion, cycle timing, range variation and paired angle differences when suitable.
- Tracking coverage estimates recorded time with usable joints. It is not accuracy. Missing measurements are unavailable, not zero.
- Optional MotionBERT analysis checks the official checkpoint hash and strictly loads the weights. The 2D/visibility input maps to H36M joints. Inference windows do not bridge tracking gaps longer than 650 ms. Report measurements then use the actual predicted 3D joints, gated by original camera visibility.
- A report compares the two earlier suitable sessions with the same exercise and source. Setup and exercise variation still need to match. Differences can include measurement error.
- This camera system does not measure pain, strength, muscle activation, fatigue, injury risk or recovery. It has not been clinically validated.

## Screens and data

Reports lead with plain-language observations and a practice focus. Technical replay and waveforms are optional expanded views. Routines have step-level reports and a separate workout summary.
Progress supports day/week/month navigation, per-exercise totals, repetition bars, measurement trends and report links. A routine counts once toward workout totals.
CSV exports include per-exercise measurements, analysis source, quality, observations and routine steps. JSON backups preserve original recordings and routine links. Period backups include whole routines that overlap the selected period. Import previews, validates, skips duplicate recordings, remaps links and discards untrusted model predictions. Backups contain original joint recordings; 3D analysis can be regenerated. Backups are capped at 100 recordings/routines and about 29 MB so exported files remain importable; use shorter periods for larger histories. CSV summaries can cover the full history.
Accounts use scrypt password hashes, opaque expiring HttpOnly session cookies, login throttling and hashed recovery codes. Recordings, routines, profiles and browser recovery drafts are scoped to the account.
The optional assistant uses the Responses API with server-held credentials. Messages are sent to the provider; a report summary is included only through the explicit checkbox. Raw video is never included. If credentials are absent, the UI says the assistant is not connected.

## Configuration

Copy `.env.example` to `.env`. Fill only integrations you want to enable, then restart the app.

Google: create a Web application OAuth client. Register `http://localhost:3000/api/auth/google/callback` as the redirect URI, and set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI`. Use the same hostname/port as the app. Test-user and consent-screen restrictions are controlled in Google Cloud. This integration cannot be verified end-to-end without your provider credentials.

Assistant: set `OPENAI_API_KEY`; `OPENAI_MODEL` defaults to `gpt-6-luna`. API billing is separate from the coding app. The key is never returned to the browser. No provider credentials are included in this project.

The supplied launcher binds to 127.0.0.1. A public deployment requires a separate deployment review, HTTPS, secure cookies, appropriate allowed hosts, server configuration and a backup strategy.

## Verification

Run:

```
npm run lint
npm test
node tests/ui-render.test.mjs
python -m unittest tests.test_direct -v
python -m unittest tests.test_platform tests.test_api.SubmissionTests tests.test_routines.RoutineTests tests.test_launch -v
```

The direct suite calls endpoints and middleware in memory and performs real checkpoint inference. The final HTTP suite requires normal local socket access. Synthetic movement tests validate software behaviour, not real-camera recognition accuracy. Browser layout, webcam trials, Google sign-in and live LLM calls require their respective runtime access and credentials.

Existing unassigned data in `data/motionai.sqlite` is preserved. It is not automatically assigned to a newly registered account. Use `python scripts/export_legacy.py` to make a JSON backup for import if you had recordings in an older installation.
