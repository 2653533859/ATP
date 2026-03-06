# MEMORY

## Recent Fixes (2026-03-06)

- Fixed device mirror auth flow by loading screenshots through Axios with token and rendering `Blob` URLs in frontend polling.
- Added `android-tools-adb` to backend runtime image so mirror screenshot endpoints can run in container deployments.
- Fixed Android low-code `clear=true` input behavior by sending repeated valid delete key events (`keyevent 67`).
- Switched APK upload path to chunked tempfile streaming to avoid loading large APK files fully into memory.
- Added regression tests for Android low-code clear behavior and APK streaming size guard.

## Validation Snapshot

- `pytest backend/tests` passed.
- `npm --prefix frontend run build` passed.

## Related Commits

- `b7f7698`: mirror/auth + clear/upload regressions.
- `c6df8fc`: latest feature repairs and task doc updates.
