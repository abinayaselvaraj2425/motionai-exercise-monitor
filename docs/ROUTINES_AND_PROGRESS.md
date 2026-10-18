# Routines and progress — October 16, 2026

## In the app
- Open **Workout routines** to start Morning routine, Full-body circuit or Standing reset.
- Guided warm-up/cooldown steps use a timer and explicit self-reported completion. They do not open the camera or claim joint measurement.
- Tracked steps use the existing camera tracker, animated demonstration and configured rep target. The camera opens when you continue to a tracked exercise (optional toggle). At the target rep count, the recording saves automatically and the routine advances to rest. Finish & save remains available for partial sets. Exercise selection is locked during routine steps.
- Take a rest between steps or continue when ready. Camera auto-start is clearly labelled and can be disabled. Camera releases during rest and guided steps. Cancelling or failing camera startup does not trigger automatic retries.
- All routines lists interrupted sessions for resuming. Completed steps and recordings survive reloads. A partly elapsed guided timer restarts when its page is left; it does not claim completion in the background.
- Finish routine creates its grouped summary. Ending early keeps actual recordings and marks unfinished steps skipped. Below-target recordings are partial, not completed steps.
- Each saved movement still supports MotionBERT analysis through its report.

## Progress
Daily, weekly and monthly views aggregate saved recordings. Week boundaries are Monday; all boundaries use the browser's local timezone. Navigation opens older complete calendar periods.

Current periods compare against the previous period through the same local clock time and weekday/day-of-month. Previous shorter months are capped at month end. Older periods compare two complete periods. Exact ranges are displayed.

Change = (current - previous) / previous * 100. No previous baseline displays new activity instead of an undefined or invented percentage. Zero activity in both periods is stated explicitly. Activity-volume changes do not measure fitness improvement or technique. Per-exercise comparisons help account for changing exercise mixes.

Camera-only recordings are the default. Imports are opt-in. Time is saved recording duration, excluding guided steps/rest. Active days count distinct local start dates. Routine completed totals count only finished runs with every step complete. Recordings spanning midnight belong to their start date.

## Storage and recovery
A finished multi-step routine counts as one workout toward the weekly goal; its individual recordings are not counted again.

The new routines table is created in the existing SQLite database without replacing existing sessions. Routine step recording UUIDs make successful saves discoverable after a reload or interrupted response. Existing recording recovery/idempotency remains in use. Test fixtures use a separate database and are never inserted into user history.

## Validation
- TypeScript strict check and production build.
- 6 routine camera lifecycle checks cover target auto-save, resource release, failed saves, recovery precedence, camera errors and opt-out. These use mocked camera/model adapters, not live accuracy measurements.
- 30 pose-engine checks; 9 camera/recovery checks; 7 calendar/comparison checks.
- 6 routine API tests (including cross-origin write protection): persistence, retry safety, step validation, full completion, early finish, partial results and deleted recording handling.
- Existing API, dataset and launcher regression suite.
- Browser checks: routine library, guided timer, rest/skip flow, resume, partial summary and period/filter controls.

This update adds orchestration and activity reporting. It does not establish real-world camera accuracy, clinical form validity or app-store certification.
