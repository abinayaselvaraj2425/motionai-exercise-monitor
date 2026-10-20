# Current verification · October 20, 2026

Passed in this workspace:

- TypeScript check (`npm run lint`).
- Production frontend build (`npm run build`).
- 31 pose-engine checks, including continuous cycles at 5–30 fps, reduced-depth movement, jitter, occlusion, side stability, plank gating and jumping-jack foot opening.
- 9 camera lifecycle/recovery checks.
- 7 calendar/progress calculation checks.
- 6 routine camera lifecycle checks, including target save, failed save and recovery precedence.
- 5 React screen-render checks: login, onboarding, progress, routine report and FAQs.
- 9 direct backend checks: account isolation and identity middleware; recovery and account deletion; coordinate-based measurements and missing visibility; rejection of upright movement as push-up analysis; two-session comparisons and trends; JSON deduplication and rejection of uploaded model output; routine backup links and CSV; request guards and malformed uploads; real MotionBERT analysis and caching.
- The official checkpoint loads strictly with 16,001,549 parameters and SHA-256 `9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f`. Real inference on a generated recording returns a 17-joint pose for each input frame, and the report uses those predictions.

Not completed here:

- The HTTP integration suite and local web preview were blocked by the execution environment's local-socket restriction. Python blocked while creating its event-loop socket before application requests ran. The hanging processes were stopped.
- Screen-render checks are not screenshots or responsive-layout verification. A full browser walkthrough, mobile sizing, and real webcam exercise trials remain to be performed after launching outside that restriction.
- Google sign-in requires the owner's OAuth credentials and consent configuration. The live provider flow has not been verified.
- The AI assistant requires an API key. Live model calls have not been made.
- These are software checks using synthetic recordings. They do not establish clinical validity or real-world exercise-recognition accuracy.

See IMPLEMENTATION.md for commands and a description of the method. The earlier VALIDATION.md is a historical record supplied in the original archive, not evidence for this update.
