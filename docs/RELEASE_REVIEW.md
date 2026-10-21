# Original-design deployment release

The visual reference is MotionAI-redesigned (2).zip. Its six stylesheets and HTML are restored byte for byte. A small component-only stylesheet gives new coaching/help content spacing using the original theme tokens. Home uses its original markup, and decorative exercise figures use the original SVG. Functional report/coaching additions remain. No Studio colour or typography overrides are loaded.

## Analysis

Live counting uses visible joint estimates and adaptive movement cycles, separately from technique feedback. This release retains the responsive counting and evidence-based report coaching developed earlier. Report coverage now excludes intervals longer than 650 ms rather than counting a portion of a camera gap. Lower sampling rates within that continuity limit are no longer automatically penalised by a 200 ms cap. These are tracking coverage estimates, not confidence in biomechanical accuracy. Side comparisons exclude frames where the selected exercise position is invalid.

MotionBERT loads the verified official weights and estimates 3D positions from recorded 2D joints. It is not a newly trained exercise classifier. A busy inference slot returns a retryable response instead of filling server threads with queued work. Failed inference preserves the recording and returns a readable error; internal details stay in server logs.

## Accounts and security

Existing password hashing, hashed session tokens, account-isolated recording stores, recovery-code rotation, Google OAuth state/PKCE/nonce checks and secure production cookies are retained. Login and recovery now have account-specific limits in addition to IP limits. Rate-limit updates and Google state consumption use serialised SQLite transactions. Cross-site browser writes are rejected even without an Origin header. Auth/chat bodies have a 100 KB limit; recordings retain the 30 MB limit. Anonymous API responses carry no-store and security headers.

The original design uses Google Fonts. Production CSP permits stylesheet access only to fonts.googleapis.com and font files from fonts.gstatic.com, alongside same-origin assets. Font requests disclose ordinary network metadata to that provider; blocked/offline fonts use the original fallback fonts.

## Chatbot

The server accepts only user/assistant text messages and strips extra fields before provider calls. Conversations have a 12,000-character input budget; the interface trims old messages as needed. Requests retain per-user rate limits and bounded output. Session summaries require explicit consent and are resolved from the signed-in account. Built-in help works without credentials. General AI answers require the owner's API key. Clearing chat removes prior shared answers from the browser's conversation.

## Deployment and validation

Use START_HERE.md and DEPLOYMENT.md. Docker builds frontend and backend into one service, verifies model/camera assets, and stores accounts and recordings on a persistent volume. Use one instance/worker. The GitHub workflow adds full HTTP integration tests and a Docker startup check; it has not run until you push it.

Local verification is recorded in STUDIO_VERIFICATION.md. Real-browser, real-person camera testing, live Google/OpenAI calls, Docker execution and a hosted restart remain separate acceptance checks. Automated fixtures and code review do not establish clinical validity, perfect recognition, or a complete security audit.
