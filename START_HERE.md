# MotionAI — original design, deployment update

This package starts from MotionAI-redesigned (2).zip, with responsive counting and detailed coaching restored.

## Try it locally

1. Extract into a new folder and open it in VS Code.
2. Run INSTALL.bat once, then START_APP.bat. Keep its terminal open.
3. Register, save your recovery code, then sign in.

If another copy occupies port 3000, stop its launcher with Ctrl+C or run:

```powershell
.\.venv\Scripts\python.exe -m backend.launch --port 3001 --open-browser
```

Keep your previous folder and its data while testing. A separate installation has separate accounts. JSON recording backups can be imported into a new account; they do not copy passwords or settings.

## What's new

- Original styles, fonts, Home layout and illustrations from MotionAI-redesigned (2).zip. The experimental Studio redesign is not used.
- Retained light/dark themes, accents, density, motion settings, photos and Home shortcuts.
- Restored adaptive reps and detailed exercise/routine coaching.
- Workspace-load recovery, safer profile uploads, improved report loading and account cleanup.
- Built-in chat help without credentials; optional OpenAI conversation when configured.
- Hosted origins, secure production cookies, browser security headers, port-aware Google callbacks and readiness checks.
- Docker, Compose and Render deployment files with persistent storage.
- Per-account login throttling, smaller auth/chat upload limits, cross-site request rejection, private error handling, and bounded chatbot history.
- Tracking gaps excluded from coverage and coaching evidence; busy model requests receive a retry message.
- GitHub checks for application tests and container startup, ready to run after upload.

## Put it online

Follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). It covers hosting, Google sign-in, chatbot keys, backups and testing. Review costs before applying the Render template, which provisions paid resources.

Copy .env.example to .env for optional local credentials. Never commit the real .env. Exercise tracking and built-in help do not require an API key.

This task has not deployed, pushed or merged this version.

## Checks and limits

See [docs/STUDIO_VERIFICATION.md](docs/STUDIO_VERIFICATION.md). Software checks and real MotionBERT inference passed. Actual browser/webcam trials, Docker build, hosted deployment and live provider calls remain to be tested outside this environment.
