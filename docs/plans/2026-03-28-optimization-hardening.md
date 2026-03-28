# Optimization Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden ATP's suite/plan execution path so invalid composition data is rejected at write time, duplicated execution logic is reduced, frontend type coverage improves, and local/runtime scaffolding is cleaned up.

**Architecture:** Keep the current product behavior and routes intact, but move more correctness checks to API write paths instead of deferring them to worker runtime. Consolidate repeated worker case-dispatch logic behind a shared helper, tighten schema/model defaults, and incrementally replace `any` in the suite/plan frontend path with domain types. Treat startup schema bootstrapping and generated artifact tracking as operational hardening, not feature work.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pydantic, Celery, Vue 3, TypeScript, pytest.

---

### Task 1: Reject invalid suite composition on create/update

**Files:**
- Modify: `backend/app/api/v1/suites.py`
- Create: `backend/tests/api/test_suites_validation.py`
- If needed: `backend/app/schemas/suite.py`

**Step 1: Write the failing test**
- Add tests proving `POST /suites` and `PATCH /suites/{id}` reject:
  - non-existent `case_id`
  - duplicate `case_id`
  - cases that belong to a different `project_id`
- Add one passing test proving valid ordered `case_ids` still persist unchanged.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_suites_validation.py -q`
- Expected: FAIL because suite handlers currently trust incoming `case_ids`.

**Step 3: Write minimal implementation**
- Add a small validation helper inside `backend/app/api/v1/suites.py` or a focused helper module.
- Load all referenced cases in one query.
- Reject missing/duplicate/cross-project cases with `400`.
- Keep the stored JSON shape `[{ "case_id": X, "sort": Y }]` unchanged.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_suites_validation.py -q`
- Expected: PASS.

### Task 2: Reject invalid plan composition on create/update

**Files:**
- Modify: `backend/app/api/v1/plans.py`
- Create: `backend/tests/api/test_plans_validation.py`
- If needed: `backend/app/schemas/plan.py`

**Step 1: Write the failing test**
- Add tests proving `POST /plans` and `PATCH /plans/{id}` reject:
  - non-existent `suite_id`
  - duplicate `suite_id`
  - suites that belong to a different `project_id`
  - invalid `env_id` for the selected project when that rule is adopted
- Add one passing test proving valid ordered `suite_ids` still persist unchanged.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_plans_validation.py -q`
- Expected: FAIL because plan handlers currently trust incoming `suite_ids`.

**Step 3: Write minimal implementation**
- Add a focused plan validation helper mirroring the suite rules.
- Validate referenced suites before commit.
- If environment/project consistency is enforced, validate `env_id` in the same helper.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_plans_validation.py -q`
- Expected: PASS.

### Task 3: Deduplicate case-type dispatch in worker execution paths

**Files:**
- Modify: `backend/app/worker/tasks.py`
- Create if needed: `backend/app/worker/case_dispatch.py`
- Modify: `backend/tests/worker/test_tasks_dispatch.py`

**Step 1: Write the failing test**
- Add or extend worker tests so one focused helper is responsible for routing:
  - API / GraphQL / WebSocket / gRPC
  - Web low-code vs script mode
  - Android low-code vs script mode
  - unsupported case type fallback
- Add one regression test proving all three call sites use the shared helper:
  - `run_test_case`
  - `run_test_suite`
  - `_execute_suite_inline`

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/worker/test_tasks_dispatch.py -q`
- Expected: FAIL because dispatch logic is duplicated across multiple functions.

**Step 3: Write minimal implementation**
- Extract a single async dispatch helper that receives `(db, run, case, extra_vars)`.
- Keep status transitions and surrounding transaction behavior in the caller.
- Reuse the helper from all three execution paths.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/worker/test_tasks_dispatch.py -q`
- Expected: PASS.

### Task 4: Replace mutable schema defaults and add schema regression coverage

**Files:**
- Modify: `backend/app/schemas/suite.py`
- Modify: `backend/app/schemas/plan.py`
- Create: `backend/tests/api/test_suite_plan_schema_defaults.py`

**Step 1: Write the failing test**
- Add schema-level tests proving list/dict fields produce fresh containers per instance:
  - suite `case_ids`
  - suite `config`
  - suite `extra_vars`
  - plan `suite_ids`
  - plan `extra_vars`
- Add one test proving serialization shape stays compatible with existing API responses.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_suite_plan_schema_defaults.py -q`
- Expected: FAIL because schemas still use literal `[]` / `{}` defaults.

**Step 3: Write minimal implementation**
- Replace mutable defaults with `Field(default_factory=list)` / `Field(default_factory=dict)`.
- Keep field names and response structure unchanged.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_suite_plan_schema_defaults.py -q`
- Expected: PASS.

### Task 5: Tighten frontend suite/plan typing and stop swallowing key load failures

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/views/suite/SuiteList.vue`
- Modify: `frontend/src/views/plan/PlanList.vue`
- If needed: `frontend/src/views/case/WebCaseDrawer.vue`
- If needed: `frontend/src/components/common/CaseFormDrawer.vue`
- Validation: `frontend/package.json`

**Step 1: Define focused frontend target**
- Introduce explicit types for:
  - `SuiteItem`
  - `SuiteRunItem`
  - `PlanItem`
  - `PlanRunItem`
  - shared select-option payloads used in suite/plan pages

**Step 2: Verify current gap**
- Run: `cd frontend && npm run type-check`
- Expected: PASS today, but type coverage on suite/plan flows is still weak because these pages rely on `any`.

**Step 3: Write minimal implementation**
- Add the new domain interfaces in `frontend/src/api/index.ts`.
- Update `suiteApi` / `planApi` method signatures to return those types.
- Replace `ref<any[]>`, `ref<any>(null)`, and `catch (e: any)` on suite/plan pages where domain types are available.
- Convert silent `catch {}` branches on key loaders into visible message or fallback handling for operator-facing paths.

**Step 4: Run validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

### Task 6: Make startup schema creation explicit and clean generated artifacts from the repo surface

**Files:**
- Modify: `backend/app/main.py`
- Modify: `README.md`
- Modify: `docs/windows-local-run.md`
- Modify: `.gitignore`
- If needed: `.env.example`

**Step 1: Define the operational rule**
- Decide whether `Base.metadata.create_all` becomes:
  - development-only behind an env flag, or
  - fully removed in favor of explicit Alembic migration steps

**Step 2: Implement minimal hardening**
- Remove or gate runtime `create_all`.
- Document the intended migration/bootstrap path in README and Windows local-run docs.
- Ignore generated beat schedule files:
  - `backend/celerybeat-schedule.bak`
  - `backend/celerybeat-schedule.dat`
  - `backend/celerybeat-schedule.dir`

**Step 3: Run focused verification**
- Run: `pytest backend/tests/api/test_case_management_api.py backend/tests/api/test_suites_validation.py backend/tests/api/test_plans_validation.py -q`
- Expected: PASS.
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

**Step 4: Manual smoke check**
- Start the backend using the documented local path.
- Verify startup fails loudly when schema is missing in environments where auto-create is disabled.
- Verify no generated beat files appear in `git status` after local scheduler activity.

### Task 7: Final focused verification and rollout note

**Files:**
- No new product files required.

**Step 1: Run focused backend regressions**
- Run: `pytest backend/tests/api/test_suites_validation.py backend/tests/api/test_plans_validation.py backend/tests/api/test_suite_plan_schema_defaults.py backend/tests/worker/test_tasks_dispatch.py backend/tests/api/test_case_step_replacement.py backend/tests/worker/test_async_runner.py -q`
- Expected: PASS.

**Step 2: Run adjacent suite/plan regressions**
- Run: `pytest backend/tests/api/test_webhook_exports_regressions.py backend/tests/plans/test_plan_regressions.py -q`
- Expected: PASS.

**Step 3: Run frontend validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

**Step 4: Summarize rollout notes**
- Record the new write-time validation rules for suite/plan composition.
- Record whether any existing invalid suite/plan records need one-time cleanup before deployment.
- Record the chosen startup migration rule so local/dev/CI environments stay aligned.
