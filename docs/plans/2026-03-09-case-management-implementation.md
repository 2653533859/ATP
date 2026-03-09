# Case Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standardized, management-first case module that lets users create cases under projects/modules, maintain normalized case content, and select approved cases for execution without breaking the current ATP execution pipeline.

**Architecture:** Extend the existing case domain instead of replacing it. Add normalized case-management fields to `TestCase`, introduce a dedicated `CaseStep` model for structured steps, preserve execution-specific configuration in `config`, and keep `TestRun` / `StepResult` as the runtime result layer. Roll the feature out in backend-first slices with focused regression tests, then update the frontend list/editor/detail flows.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, Pydantic, Vue 3, TypeScript, pytest.

---

### Task 1: Define backend case management schema

**Files:**
- Modify: `backend/app/models/case.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/bootstrap.py`
- Create: `backend/alembic/versions/20260309_0009_standardize_case_management.py`
- Test: `backend/tests/api/test_case_management_schema.py`

**Step 1: Write the failing test**
- Add schema-level tests that prove the new `TestCase` fields and `CaseStep` relationship exist and behave as expected.
- Add a test that proves project/module codes can be persisted if required by the chosen code-generation strategy.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_case_management_schema.py -q`
- Expected: FAIL because the new fields/models/migration do not exist yet.

**Step 3: Write minimal implementation**
- Add standardized management fields to `TestCase`.
- Add `CaseStep` model and relationship wiring.
- Add migration for the new schema.
- Keep existing runtime models intact.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_case_management_schema.py -q`
- Expected: PASS.

### Task 2: Extend case schemas and API contract

**Files:**
- Modify: `backend/app/schemas/case.py`
- Modify: `backend/app/api/v1/cases.py`
- Test: `backend/tests/api/test_case_management_api.py`

**Step 1: Write the failing test**
- Add API tests for create/read/update flows using standardized fields and ordered steps.
- Add list-filter tests for `priority`, `review_status`, `keyword`, and project/module scope.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_case_management_api.py -q`
- Expected: FAIL because request/response schemas do not yet include the new fields.

**Step 3: Write minimal implementation**
- Add create/update/detail/list schemas for standardized case data.
- Update `/cases` handlers to read/write structured steps and new metadata.
- Keep current execution endpoint contract stable.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_case_management_api.py -q`
- Expected: PASS.

### Task 3: Add review workflow endpoints

**Files:**
- Modify: `backend/app/api/v1/cases.py`
- Modify: `backend/app/schemas/case.py`
- Test: `backend/tests/api/test_case_review_workflow.py`

**Step 1: Write the failing test**
- Add tests for `submit-review`, `approve`, `reject`, `deprecate`, and `reactivate` transitions.
- Add tests for invalid state transitions.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_case_review_workflow.py -q`
- Expected: FAIL because workflow endpoints and guards are missing.

**Step 3: Write minimal implementation**
- Implement workflow action endpoints.
- Enforce transition rules in the case API layer or a small service helper.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_case_review_workflow.py -q`
- Expected: PASS.

### Task 4: Preserve snapshots for standardized cases

**Files:**
- Modify: `backend/app/models/case.py`
- Modify: `backend/app/api/v1/cases.py`
- Test: `backend/tests/api/test_case_snapshots.py`

**Step 1: Write the failing test**
- Extend snapshot tests so they prove standardized fields and steps are preserved in snapshots and restored on rollback.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_case_snapshots.py -q`
- Expected: FAIL because snapshot coverage is incomplete for the new case structure.

**Step 3: Write minimal implementation**
- Update snapshot creation and rollback logic to capture and restore standardized content.
- Prefer a compact JSON snapshot payload rather than duplicating step tables for history.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_case_snapshots.py -q`
- Expected: PASS.

### Task 5: Update frontend API types and list page

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/views/case/CaseList.vue`
- If needed: `frontend/src/router/index.ts`
- Validation: `frontend/package.json`

**Step 1: Define focused validation target**
- Use type-check / build validation if no frontend unit-test harness exists.

**Step 2: Verify current gap**
- Run: `cd frontend && npm run type-check`
- Expected: current code does not yet support the new case-management fields end-to-end.

**Step 3: Write minimal implementation**
- Extend frontend case types and requests.
- Update case list columns and filters to show management-first fields.
- Keep UI changes scoped to the case module.

**Step 4: Re-run validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS, or document unrelated blockers if they remain outside this scope.

### Task 6: Build standardized case editor and detail flow

**Files:**
- Modify: `frontend/src/views/case/CaseList.vue`
- Modify: `frontend/src/views/case/AndroidCaseDrawer.vue`
- Create if needed: `frontend/src/views/case/CaseDetail.vue`
- Create if needed: `frontend/src/components/case/CaseStepEditor.vue`
- Validation: `frontend/package.json`

**Step 1: Define the failing validation target**
- Use type-check/build validation and manual route-level smoke verification if no component tests exist.

**Step 2: Verify current gap**
- Run: `cd frontend && npm run type-check`
- Expected: the current editor/detail experience is insufficient for structured case management.

**Step 3: Write minimal implementation**
- Add sectioned editor for basic info, preconditions, steps, and automation binding.
- Add structured step editing.
- Add a read-oriented case detail page if needed.

**Step 4: Re-run validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS, or document unrelated blockers.

### Task 7: Gate execution by case readiness

**Files:**
- Modify: `backend/app/api/v1/cases.py`
- Modify: `frontend/src/views/case/CaseList.vue`
- Test: `backend/tests/api/test_case_execution_guards.py`

**Step 1: Write the failing test**
- Add tests that prove draft/unapproved/manual-only cases are blocked or clearly handled according to the approved business rules.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_case_execution_guards.py -q`
- Expected: FAIL because the readiness gate is not enforced yet.

**Step 3: Write minimal implementation**
- Add backend validation for execution readiness.
- Reflect those rules in frontend action availability.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_case_execution_guards.py -q`
- Expected: PASS.

### Task 8: Final focused verification

**Files:**
- No new product files required.

**Step 1: Run focused backend suite**
- Run: `pytest backend/tests/api/test_case_management_schema.py backend/tests/api/test_case_management_api.py backend/tests/api/test_case_review_workflow.py backend/tests/api/test_case_execution_guards.py backend/tests/api/test_case_snapshots.py -q`
- Expected: PASS.

**Step 2: Run adjacent existing regressions**
- Run: `pytest backend/tests/api/test_case_filters.py backend/tests/api/test_projects_modules.py -q`
- Expected: PASS.

**Step 3: Run frontend validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS, or document unrelated blockers outside this feature.

**Step 4: Summarize rollout notes**
- Record legacy-case compatibility behavior.
- Record whether any manual backfill is needed for historical cases.
