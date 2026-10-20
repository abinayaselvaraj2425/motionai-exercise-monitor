# Put MotionAI online

This is a React website with a Python API and a CPU machine-learning model. Deploy both parts together using the supplied Dockerfile. A static host such as GitHub Pages alone cannot run the backend.

The project is prepared for deployment, but no hosting resources have been created and no live Google/OpenAI credentials have been configured or verified. Review your hosting and API costs before enabling paid resources.

## 1. Test the new version locally

Extract into a new folder. In that folder, run INSTALL.bat once, then START_APP.bat. Keep the terminal open. If an older copy is using port 3000, stop its launcher with Ctrl+C or use:

```powershell
.\.venv\Scripts\python.exe -m backend.launch --port 3001 --open-browser
```

This installation uses its own account data. Keep the old folder. JSON recording backups can be imported into a new account; they do not copy account passwords or settings.

## 2. Add the updated source to your GitHub repository

Use a new branch and pull request so your teammate can review the changes. The Dockerfile, render.yaml, requirements.txt, backend, scripts, public/favicon.svg and frontend source must be in the project root together. Keep the supplied .gitignore. Do not upload .env, account databases, node_modules, .venv or recordings. The image build downloads and verifies the camera assets and official MotionBERT checkpoint, so those large files do not need to be committed.

This task has not pushed or merged this version on GitHub.

## 3. Deploy the Docker web service on Render

1. Sign in to Render and connect the GitHub repository containing the updated project.
2. Create a Docker web service with the project folder as its root. The Dockerfile builds React and serves it from the same FastAPI origin.
3. Choose a paid instance with enough memory for CPU PyTorch. The supplied Blueprint uses the 1c-2g plan as a starting point; monitor memory, response times and actual cost. This is not a capacity guarantee.
4. Add a persistent disk mounted at `/var/data`. The template requests 5 GB. Account databases and joint recordings live here, not in the image. Without persistent storage, restarts and deployments can lose your recordings.
5. Set the health-check path to `/healthz`. This reports ready only when the camera assets and required model are ready. First build downloads and verifies the model; allow time for the build and initial startup.
6. The Dockerfile already sets the production environment, persistent data paths and one server worker. Set `FORWARDED_ALLOW_IPS=*` on Render, whose proxy fronts this service. On another host, trust only its actual reverse proxy addresses.
7. Render supplies its HTTPS URL automatically. The application uses that origin by default. For a custom domain, set `MOTIONAI_PUBLIC_URL=https://your-domain.example` with no trailing path, and configure that domain on the host first.
8. Deploy. Open the HTTPS website, register, save your recovery code and sign in. Camera access requires HTTPS on a public website.

You can alternatively use New Blueprint with the included render.yaml. It provisions a paid service and disk; inspect the plan and environment fields before approving it. Optional provider credentials can be added later if you only want built-in help initially.

Use one service instance and one Uvicorn worker with the current local SQLite storage. Horizontal scaling needs a shared database, shared recordings/object storage and shared inference/rate-limiting infrastructure first.

## 4. Enable Google sign-in

1. In Google Cloud Console, create or select a project. Configure Google Auth Platform branding, audience and the requested basic identity scopes.
2. Create an OAuth client of type Web application.
3. Add your exact website origin if the console asks for authorised JavaScript origins, for example `https://your-app.onrender.com`.
4. Add the authorised redirect URI exactly:

```text
https://your-app.onrender.com/api/auth/google/callback
```

5. In the hosting service's environment, set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Keep the secret on the server. The callback is derived from your public URL, or you can set `GOOGLE_REDIRECT_URI` explicitly to the exact address above.
6. Redeploy/restart, then test Continue with Google in a fresh browser session. While the Google consent app is in testing, add the intended accounts as test users. Follow Google's publishing/verification requirements before opening it to a wider audience.

For local testing, register a separate development callback such as `http://localhost:3001/api/auth/google/callback`. The local launcher now derives the callback from its selected port. Use a separate production OAuth client for the public website.

The application checks one-time OAuth state, PKCE, issuer, audience, expiration and nonce. Automated tests mock the Google token endpoint; your actual OAuth project must still be tested.

## 5. Connect the AI chatbot

Without credentials, the chat panel explicitly uses built-in MotionAI help. It can explain tracking, reports, progress and exports. It does not pretend to answer general questions using AI.

For broader, conversational answers:

1. Create an OpenAI API key in your own API project and configure billing and spending limits there. A ChatGPT subscription is separate from API usage.
2. Add `OPENAI_API_KEY` to the hosting service's secret environment variables.
3. Set `OPENAI_MODEL=gpt-4.1-mini`, or another Responses-compatible text model available to your API project.
4. Redeploy/restart. The chat panel will show AI connected. Ask a general question, an app question and a follow-up.
5. To discuss a saved session, open that report and select Include this report's summary. Messages and the selected summary are then sent to the provider. Raw video is not sent by this integration.

The server uses the Responses API with `store:false`; this setting is not a promise of zero provider retention under every account policy. Never put API keys in React code or commit them to GitHub. Provider errors and usage limits now produce readable messages without exposing the key.

The provider request/response format and failure handling were checked with mocks. No billable API calls were made during this implementation.

## 6. Test before sharing

- Register, log out, sign back in and check that a second account cannot see the first account's sessions.
- Exercise on at least two devices and with different users. Confirm rep counting, posture cues, pause/resume, saving and routine transitions.
- Open a saved report, run MotionBERT, and verify the optional 3D replay and angle measurements.
- Select previous days/weeks/months, open the corresponding reports, export CSV and round-trip a JSON recording backup.
- Test light/dark themes, phone widths, keyboard navigation and reduced motion in an actual browser.
- Verify Google login and an AI question using the real configured providers.
- Restart/redeploy and confirm that accounts and recordings remain. Keep independent database-consistent backups; use SQLite's backup API while the service runs, or copy the complete data directory while stopped.

Local software checks do not prove clinical accuracy or recognition accuracy across all people. MotionBERT estimates joint positions; adaptive rules generate counts and coaching. A counted repetition is not a certification of correct form.

## Docker on your own computer

With Docker Desktop installed:

```powershell
docker compose up --build
```

This starts a local HTTP app at localhost:3000 and stores recordings in the named volume. Optional .env variables are used by Compose. Do not delete the volume if you want to keep recordings. For public hosting, place the service behind HTTPS, set the production environment and public origin, and configure trusted proxy addresses.

Docker is not installed in the implementation environment, so the image has not been built or launched here. The files were checked for consistent paths, YAML structure and entry points.

## Official references

- [Render Docker deployment](https://render.com/docs/docker)
- [Render persistent storage](https://render.com/docs/disks)
- [Render default environment variables](https://render.com/docs/environment-variables)
- [Render compute plans](https://render.com/docs/compute-plans)
- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [OpenAI text generation and Responses API](https://developers.openai.com/api/docs/guides/text)
