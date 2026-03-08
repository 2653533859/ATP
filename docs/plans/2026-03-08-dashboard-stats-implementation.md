# Dashboard Stats Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make dashboard overview stats respect the selected day range and clear stale sections when stats requests fail.

**Architecture:** Extend the backend overview API with a `days` filter for run-based metrics, keep the fixed 7-day card intact, and make each frontend loader reset only its own state on failure.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Vue 3, TypeScript, pytest.

---

### Task 1: Cover overview day-range behavior

**Files:**
- Create: `backend/tests/api/test_statistics.py`
- Modify: `backend/app/api/v1/statistics.py`

**Step 1: Write the failing test**
- Add a regression test for `get_overview()` that passes `days=30` and proves the selected range is used for run totals while the fixed 7-day summary still uses 7 days.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_statistics.py -q`
- Expected: FAIL because `get_overview()` does not yet accept or use `days`.

**Step 3: Write minimal implementation**
- Add `days` to `/statistics/overview`.
- Filter the run total/pass-rate query by `created_at >= _since(days)`.
- Keep `recent_runs_7d` using `_since(7)`.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_statistics.py -q`
- Expected: PASS.

### Task 2: Fix dashboard stale-state handling

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/views/dashboard/DashboardView.vue`

**Step 1: Prepare verification target**
- Use focused frontend validation because no unit-test harness exists in this repo.

**Step 2: Implement minimal frontend changes**
- Pass `days` into `statisticsApi.overview()`.
- Reset overview/charts to empty defaults in each loader catch block.

**Step 3: Run focused validation**
- Run: `npm run type-check`
- Expected: PASS for the touched dashboard files, or document unrelated workspace blockers if they exist.

### Task 3: Final verification

**Files:**
- No new product files required.

**Step 1: Run focused regression tests**
- Run: `pytest backend/tests/api/test_statistics.py -q`

**Step 2: Run frontend validation**
- Run: `npm run type-check`

**Step 3: Summarize any unrelated blockers**
- Report only problems not introduced by this patch.
