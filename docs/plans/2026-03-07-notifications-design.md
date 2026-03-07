# 4.5 Notifications Design

**Date:** 2026-03-07
**Scope:** Complete Phase 4.5 notification integration with a minimal, production-oriented finish.

## Goal

Finish the existing notification feature set so projects can configure email, WeCom bot, and DingTalk bot channels; trigger test sends from the UI; and automatically send execution summaries after suite and plan runs.

## Current State

The repository already contains most of the notification skeleton:
- Backend model/schema/API for notification configs
- Notification sending service for SMTP, WeCom, and DingTalk
- Frontend notification management page and API wrapper
- Suite and plan worker hooks that attempt to send notifications

The main gaps are delivery readiness, schema/bootstrap reliability, focused tests, and a few frontend correctness issues.

## Approved Delivery Scope (Scheme A)

1. Make notification persistence reliable in first-start and migration-driven environments.
2. Add focused backend tests for notification API/service behavior.
3. Fix obvious frontend notification page correctness issues without broad UI redesign.
4. Document required SMTP environment variables and notification setup notes.
5. Keep current trigger scope limited to suite runs and plan runs.

## Non-Goals

- No retry queue, dead-letter handling, or delivery audit log.
- No per-channel template customization.
- No per-trigger filtering rules.
- No single-case notification trigger in this phase.

## Design

### Backend

- Ensure `NotificationConfig` is loaded into SQLAlchemy metadata during app startup so `Base.metadata.create_all()` includes the notification table in bootstrap scenarios.
- Keep the existing API surface intact to avoid frontend contract churn.
- Harden notification tests around:
  - config CRUD basics where practical
  - test-send dispatch by channel
  - formatting helpers and DingTalk signature path
- Preserve current failure isolation: notification send failures must not break suite/plan completion.

### Frontend

- Keep the existing page structure.
- Fix notification-form typing/correctness issues so the page is maintainable and compiles once unrelated workspace issues are resolved.
- Keep UX simple: select project, list configs, create/edit/delete, test send.

### Documentation

- Add SMTP variables to `.env.example`.
- Add a short notification setup section to `README.md` or equivalent root docs.

## Future Extensions

### Scheme B: Standard Completion

- Trigger notifications for single case runs as well as suite and plan runs.
- Add stronger frontend field validation and clearer test-send feedback.
- Add more explicit trigger-type labeling in notification content.

### Scheme C: Enhanced Notifications

- Add retry/backoff and better failure reporting.
- Add delivery history / audit records.
- Add notification policies by trigger type, result status, and project scope.
- Add richer templating and per-channel customization.

## Testing Strategy

- Add targeted backend regression tests first.
- Verify tests fail before implementation.
- Run focused tests for notification behavior after implementation.
- Avoid broad unrelated fixes outside 4.5 scope.
