# Q9 Acceptance Summary

> Date: 2026-05-30

Q9 is functionally complete across the two P0 tracks (Release Readiness, AI Production Feedback Loop) and the three P1 tracks (Dataset v2 governance, Performance Center productization, Q8 capability product hardening). This document records the acceptance scope, the Phase 5 hardening changes, verification evidence, and known follow-up risks.

## Completed Scope

### Phase 1 — Release Readiness and CI/CD Hardening (P0-1)

- Full backend regression command fixed as a stable CI baseline.
- Docker image build checks for backend / worker / frontend, with mandatory worker `k6 version` validation.
- Alembic zero-state upgrade, head check, and migrate Job gates folded into the release checklist.
- Staging dry-run checklist produced.

Key artifacts:

- `docs/q9-release-checklist.md`
- `docs/q9-release-evidence.md`
- `.github/workflows/release-readiness.yml`

### Phase 2 — AI Production Feedback Loop (P0-2)

- AI healing adoption / rollback / regression pass-rate aggregated into a queryable report.
- AI case generation draft funnel (generated → saved / abandoned) statistics.
- AI stats page extended with production feedback dimensions.
- Prompt example selection strategy weighted by adoption quality and case type.

Key artifacts:

- `backend/app/services/ai_healing_stats.py`
- `backend/app/services/ai_case/funnel.py`
- `backend/app/services/healing_prompt_examples.py`
- `frontend/src/views/system/AIHealingStatsView.vue`

### Phase 3 — Dataset v2 Governance (P1-1)

- Upload validation policy: default soft-block, project-configurable hard-block.
- Dataset version history and rollback.
- Reference impact query (cases / suites / plans / AI drafts).
- Optional strict schema enforcement for parameterized execution.

Key artifacts:

- `backend/app/services/dataset_schema.py`
- `frontend/src/views/system/DatasetLibrary.vue`
- `docs/dataset-v2.md`

### Phase 4 — Performance Center Productization (P1-2)

- Target allowlist and max VUs / duration backend limits.
- Helm values example for a dedicated performance worker.
- Load-test trend charts and run comparison.
- Raw summary lifecycle and cleanup policy.

Key artifacts:

- `backend/app/services/storage_cleanup.py`
- `frontend/src/views/system/PerformanceCenterView.vue`
- `deploy/helm/atp/values.yaml`

### Phase 5 — Product Hardening and Documentation Closure (P1-3)

This phase aligns the new Q8/Q9 entry points with the platform's permission, empty, error, and loading conventions, and closes out the documentation.

State scan of the four new surfaces (`PerformanceCenterView`, `DatasetLibrary`, `AIGenerateDrawer`, `AIHealingStatsView`):

- Loading / error states are in place across all four (a-spin, try/catch with `message.error`).
- `DatasetLibrary` already carries a table empty state via `:locale="{ emptyText: t('dataset.empty') }"`.
- `PerformanceCenterView` already carries empty states (e.g. threshold table `a-empty`).
- `AIHealingStatsView` error-fingerprint table had no explicit empty text; a Chinese empty text was added.

Permission finding and fix (the most material item surfaced by the scan):

- The router guard previously only checked the auth token and **never consumed `meta.requireAdmin`**. Admin-only pages (`ai-healing-stats`, `healing-examples`, `audit-logs`, `run-retention`, `dashboard-alerts`) were reachable by non-admin users via a direct URL; the `v-if` menu checks only hid the entry, not the route.
- Because `user` is only populated by `fetchMe()` (login / `RunDetail`), a page refresh dropped `user` to null — also hiding the admin menu and username in `MainLayout`.
- The guard is now `async`: when a token exists but `user` is unloaded it awaits `fetchMe()` first, then enforces `requireAdmin` (non-admin is bounced to the dashboard with an error toast). This fixes both the privilege-escalation gap and the refresh-time user-loss bug in one change.

Key artifacts:

- `frontend/src/router/index.ts`
- `frontend/src/views/system/AIHealingStatsView.vue`
- `README.md` (Q8/Q9 capability index)
- `docs/q9-acceptance-summary.md`

## Verification Evidence

Latest full validation (HEAD `9a05ab5` + Phase 5 working-tree changes):

```text
backend full regression (excl. integration): 726 passed, 2 skipped, 41 warnings in 11.84s
frontend type-check (vue-tsc --noEmit): passed
```

The 41 warnings are all `PytestCollectionWarning` for SQLAlchemy/Pydantic classes named `Test*` (TestSuite, TestCase, TestRun, TestDataset) and are not failures.

Frontend production build was last verified in `docs/q9-release-evidence.md` (local pass); rebuild it in CI before tagging.

Backend full regression command:

```bash
python -m pytest backend/tests --ignore=backend/tests/integration -q
```

Frontend type-check command:

```bash
cd frontend
npm run type-check
```

## Backend Permission Audit (2026-05-30)

A follow-up audit verified backend authorization for every admin-only surface exposed in the frontend. Result: **no privilege-escalation gap** — all five surfaces are correctly guarded.

| Surface | Backend endpoint(s) | Guard | Contract test |
|---------|---------------------|-------|---------------|
| ai-healing-stats | `ai_healing_stats.py` | `require_admin` | `test_ai_healing_stats_api.py` |
| healing-examples | `healing_prompt_examples.py` (4) | `require_admin` | `test_healing_prompt_examples_api.py` |
| audit-logs | `projects.py::list_audit_logs` | `require_admin` | `test_audit_logs_api.py` (new) |
| run-retention | `admin_runs.py` (3) | `require_admin` | `test_admin_runs_api.py` (extended) |
| dashboard-alerts | `dashboard_alerts.py` (7) | `require_engineer` + project owner/viewer | `test_dashboard_alerts.py` |

`dashboard-alerts` intentionally uses project-level RBAC instead of global admin, because alert rules are project-scoped resources. The frontend marks that page `requireAdmin` (stricter than the backend) — a UI over-restriction, not a security gap; aligning the granularity is a product decision deferred for later.

This audit closed the only missing permission-contract test (`audit-logs`) and extended `test_admin_runs_api.py` to cover the `per-project-preview` endpoint.

## Known Follow-Ups

- Run the full backend regression and the `release-readiness` workflow in Docker-enabled CI before release tagging (see `docs/q9-release-evidence.md` pending section).
- Rebuild worker images in CI to verify the k6 multi-stage path and `k6 version`.
- `AIGenerateDrawer` keeps its current error handling; richer loading/empty affordances inside the drawer are deferred as a low-impact follow-up.
- Resolved (2026-05-30): backend admin-permission audit completed — see "Backend Permission Audit" above; permission-contract tests now cover all five admin surfaces.
- Continue feeding production AI healing adoption metrics back into iter5 thresholds and prompt examples.
