# MEMORY

## Recent Fixes (2026-03-08)

- Completed Phase 4.5 notification integration across backend, frontend, migration, and docs.
- Added notification config model/schema/API/service, notification settings UI, and SMTP-related environment documentation.
- Added regression tests for notification dispatch, notification API test-send behavior, startup model loading, and migration coverage.
- Fixed notification read-path credential exposure by requiring engineer-level access for notification detail/list endpoints.
- Fixed WeCom and DingTalk delivery handling so non-200 responses or non-zero `errcode` values now raise errors instead of being reported as success.
- Fixed project deletion regression by cascading `notification_configs` on project delete at both ORM and migration/foreign-key levels.
- Restored frontend type-check by installing missing `vuedraggable` / `sortablejs` dependencies.
- Updated `Task.md` to mark 4.5 notification integration complete and recorded the security/correctness hardening items.

## Previous Fixes (2026-03-06)

- Fixed device mirror auth flow by loading screenshots through Axios with token and rendering `Blob` URLs in frontend polling.
- Added `android-tools-adb` to backend runtime image so mirror screenshot endpoints can run in container deployments.
- Fixed Android low-code `clear=true` input behavior by sending repeated valid delete key events (`keyevent 67`).
- Switched APK upload path to chunked tempfile streaming to avoid loading large APK files fully into memory.
- Added regression tests for Android low-code clear behavior and APK streaming size guard.

## Validation Snapshot

- `pytest backend/tests/api/test_notifications.py backend/tests/services/test_notifier.py backend/tests/migrations/test_notification_config_migration.py backend/tests/services/test_notification_bootstrap.py backend/tests/plans/test_plan_regressions.py backend/tests/api/test_webhook_exports_regressions.py -q` passed (`20 passed`).
- `npm --prefix frontend run type-check` passed after restoring missing frontend dependencies.

## Related Commits

- `a970cd2`: notification integration, security fixes, Task update, and supporting docs/tests.
- `b7f7698`: mirror/auth + clear/upload regressions.
- `c6df8fc`: latest feature repairs and task doc updates.
