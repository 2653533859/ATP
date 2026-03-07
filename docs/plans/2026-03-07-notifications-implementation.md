# Notifications Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish Phase 4.5 notifications with minimal-risk backend, frontend, and documentation updates.

**Architecture:** Reuse the existing notification API/service/UI, add focused regression tests first, then apply the smallest changes needed to make notification bootstrap, dispatch testing, and documentation reliable.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Celery, Vue 3, TypeScript, pytest.

---

### Task 1: Cover backend notification dispatch

**Files:**
- Create: `backend/tests/services/test_notifier.py`
- Modify: `backend/app/services/notifier.py`

**Step 1: Write the failing test**
- Add tests for summary formatting and DingTalk signed webhook generation.
- Add tests that prove channel dispatch calls the expected sender.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/services/test_notifier.py -q`
- Expected: FAIL because current behavior is incomplete or unverified.

**Step 3: Write minimal implementation**
- Adjust notifier helpers only where tests require it.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/services/test_notifier.py -q`
- Expected: PASS.

### Task 2: Cover notification API test-send behavior

**Files:**
- Create: `backend/tests/api/test_notifications.py`
- Modify: `backend/app/api/v1/notifications.py`

**Step 1: Write the failing test**
- Add tests for unknown config 404 and per-channel test-send dispatch.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_notifications.py -q`
- Expected: FAIL with missing behavior or import/setup issues.

**Step 3: Write minimal implementation**
- Keep API contract stable; only fix what tests reveal.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_notifications.py -q`
- Expected: PASS.

### Task 3: Fix notification bootstrap and docs

**Files:**
- Modify: `backend/app/main.py`
- Modify: `.env.example`
- Modify: `README.md`

**Step 1: Write the failing test**
- Add a regression assertion in an existing focused backend test that checks notification model metadata is loaded by startup imports, or create a small bootstrap test if needed.

**Step 2: Run test to verify it fails**
- Run the focused test.

**Step 3: Write minimal implementation**
- Import notification model at startup.
- Document SMTP variables and setup notes.

**Step 4: Run test to verify it passes**
- Run the focused test plus notification tests.

### Task 4: Fix frontend notification page correctness

**Files:**
- Modify: `frontend/src/views/system/NotificationList.vue`

**Step 1: Write the failing test**
- If no frontend test harness exists, use compile-oriented validation as the safety check and keep edits minimal.

**Step 2: Run validation to verify current issue**
- Run a focused type-check or note current unrelated workspace blockers.

**Step 3: Write minimal implementation**
- Fix obvious typing issues and keep current UI behavior.

**Step 4: Run validation**
- Re-run focused validation if possible; otherwise document the unrelated blockers.

### Task 5: Final verification

**Files:**
- No new product files required.

**Step 1: Run focused backend tests**
- Run: `pytest backend/tests/services/test_notifier.py backend/tests/api/test_notifications.py -q`

**Step 2: Run adjacent regression tests**
- Run: `pytest backend/tests/plans/test_plan_regressions.py backend/tests/api/test_webhook_exports_regressions.py -q`

**Step 3: Summarize remaining known issues**
- Call out unrelated frontend dependency/build blockers separately.
