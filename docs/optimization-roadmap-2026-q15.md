# ATP Optimization Roadmap 2026 Q15

> Status: **draft, partially executed**. Measured inputs are from 2026-07-31.
> Q15-01 (local scope) / Q15-02 / Q15-03 / Q15-05 / Q15-06 landed on 2026-08-01;
> Q15-04 and Q15-07 are still open and Q15-00 still waits on environment access.
> See the Execution Log at the bottom for what changed against this plan.

## Goal

Q15 has no new product direction. Q10-Q14 built a quality apparatus — ruff, mypy,
bandit, coverage gates, pre-commit, integration/E2E/security workflows — and Q13/Q14
drove backend coverage from 53% to 82.73% and frontend from 4.38% to 21.48%. The
apparatus is now larger than the enforcement behind it: on 2026-07-31 a clean checkout
of `main` failed both `make format-check` and `make mypy`, and the offending commits
had been sitting on `main` since 2026-07-11 with the same checks green in
`.github/workflows/ci.yml` since 2026-07-08.

So Q15 turns the apparatus from *declared* into *binding*, and closes the two
structural gaps that let defects through it: backend tests that only pass in whole-suite
order, and the absence of any Windows job despite the repo shipping Windows run
instructions. It then continues the coverage arc into the tiers Q14 explicitly left out
(the `views/system` page family, the worker maintenance tasks) and publishes the Q14
acceptance summary that Q10/Q11/Q13 all have. Q14-00 (the environment-blocked Q12-05
captures) carries forward unchanged and interrupts the moment access is available.

## Planning inputs (measured 2026-07-31)

- **Gates declared but not binding.** `ci.yml` has run `ruff format --check` and `mypy`
  since `1efc10c` (2026-07-08). The Q13/Q14 coverage commits of 2026-07-11 (`c925df1`,
  `c35542d`, `fab2bdd` and siblings) introduced 16 unformatted files and 12 mypy
  arg-type errors in `services/run_retention.py`; both survived on `main` for 20 days
  until `e76bd24` / `d116359`. `.git/hooks/pre-commit` is not installed in the working
  clone, and `.git-blame-ignore-revs` carried its "append the commit SHA here"
  instruction from Q10 until `fcd42c9` without ever receiving one. Branch-protection
  state could not be inspected (no authenticated `gh` in this environment) — confirming
  whether `main` has required status checks is the first task of Q15-01.
- **Backend tests are order-dependent.** Running each of the 183 non-integration test
  files on its own, **10 fail** (5.5%), in three groups:
  - 8 files raise `ModuleNotFoundError: No module named 'app'` — they rely on another
    test module having inserted `backend/` into `sys.path`
    (`api/test_case_execution_guards.py`, `api/test_webhook_exports_regressions.py`,
    `services/test_ai_case_funnel.py`, `services/test_dashboard_alert_service.py`,
    `services/test_performance_runner.py`, `services/test_performance_summary.py`,
    `worker/test_plan_execution_config.py`, `worker/test_suite_execution_config.py`).
    `backend/tests/_paths.py` already exists for cwd-independent root location but does
    not cover `sys.path` bootstrap.
  - `api/test_mock_d2.py` raises `ImportError: cannot import name
    'assert_project_access'` — the root conftest stubs `app.api.deps` with only
    `get_current_user` / `require_engineer` / `require_admin`, so any module importing
    `assert_project_access` or `require_project_access` needs an earlier test file to
    have hard-set a richer stub.
  - `test_conftest_stubs.py` — the contract test for the stub mechanism itself — fails
    4/5 standalone with `ModuleNotFoundError: No module named 'tests'`.
  A single instance of this class was fixed in `d116359`
  (`services/test_run_retention.py` needed `load_all_models()`); the remaining 10 are
  untouched. `pytest backend/tests/<file>` is a documented workflow in CLAUDE.md, so
  each of these is a broken documented entry point.
- **No Windows job.** `docs/windows-local-run.md` and `scripts/windows-local.ps1` make
  Windows a supported development platform, but every workflow in `.github/workflows/`
  runs on Linux only. The first full-suite run ever executed on Windows (2026-07-31)
  surfaced `worker/test_q12_evidence_collector.py` failing because the fake matched
  `endswith("scripts/android-network-doctor.sh")` while `collect-q12-evidence.py:817`
  builds that argument with pathlib (fixed in `d116359`). A follow-up scan found the
  other four `endswith("<path>/…")` assertions in the suite are URL paths, not
  filesystem paths, so the *known* blast radius was one test — but nothing prevents the
  next one, and no one would learn about it from CI.
- **Backend coverage TOTAL 82.73%** (13962 statements, 2045 missed), `1327 passed`, CI
  gate 70 — 12.7 points of headroom, so the gate no longer tracks reality. Modules still
  below 60%:
  `worker/tasks_performance.py` **0%** (43 missed — the k6 task has no test at all),
  `services/mobile_special/aggregator.py` 9% (24),
  `services/ai_healing_stats.py` 26% (51), `services/device_sync.py` 39% (14),
  `worker/tasks_db_backup.py` 44% (52), `worker/tasks_device.py` 52% (11),
  `services/dashboard_alerts.py` 56% (42), `worker/tasks_healing.py` 56% (17),
  `worker/celery_app.py` 57% (13, mostly signal handlers).
- **Frontend statements 21.48%** (1913/8904), branches 18.48%, functions 17.44%,
  lines 22%; gates 20.5 / 17.5 / 16.5 / 21.0. Q14-03 covered five workbench views; the
  largest remaining zero-coverage pool is the `views/system` family at **2.54%** — 11 of
  its 12 pages are at 0% (`DatasetLibrary.vue` 727 lines, `ReportCenterView.vue` 674,
  `StorageManagementView.vue` 474, `NotificationList.vue` 425, `BugTrackerList.vue` 405,
  `MockRulesView.vue` 404, `AILLMConfigList.vue` 345, `VariableLibrary.vue` 280,
  `RunRetentionView.vue` 244, `AIHealingStatsView.vue` 198,
  `HealingPromptExamplesView.vue` 189; only `EnvironmentList.vue` is covered at 33.98%).
  Also fully uncovered: all three `views/mobile-special` pages (470 / 463 / 384),
  `views/project` (244 + 221), `views/mock/MockRuleList.vue` (532),
  `views/audit/AuditLogList.vue` (157), `views/run/RunList.vue` (199), and five of six
  `views/case` drawers (`AIGenerateDrawer.vue` 626, `CaseDetail.vue` 582,
  `WebCaseDrawer.vue` 501, `AndroidCaseDrawer.vue` 416, `CaseHistoryDrawer.vue` 226).
- **One load-sensitive frontend test.** `src/utils/chartTheme.spec.ts` failed twice on
  2026-07-31 when run concurrently with other work, both times
  `Test timed out in 5000ms` on `await import('@/utils/chartTheme')`; the import took
  16.2s under load versus ~100ms idle. It passes in isolation and in an unloaded full
  run (`102 passed`). It is not registered in `docs/flaky-governance.md`, which the
  `flaky` marker policy requires.
- **Q14 has no acceptance summary.** Q10, Q11 and Q13 each have
  `docs/q*-acceptance-summary.md`; Q14 has only `docs/q14-completion-audit.md`, which is
  an evidence table rather than the narrative summary the other quarters publish.

## Work Items

| ID | Work item | Acceptance criteria | Status |
| --- | --- | --- | --- |
| Q15-00 | Close Q12-05 captures + publish Q12 acceptance | Carried from Q14-00 unchanged: when environment access arrives, dated `docs/slo-history-*.md` and `docs/android-device-rehearsal-*.md` per the frozen spec in `docs/q12-external-readiness-evidence.md`, then `make validate-q12-evidence` and `docs/q12-acceptance-summary.md` | Blocked on environment (carried from Q13-00 → Q14-00) |
| Q15-01 | Make the declared gates binding | Branch-protection state on `main` documented and required status checks enabled for the `ci.yml` jobs (or, if protection is unavailable on the plan, an equivalent documented pre-push path); `pre-commit install` added to `make setup` and to the CLAUDE.md/AGENTS.md verification sections; the `.pre-commit-config.yaml` mypy hook stops depending on ambient `PATH` python; a regression asserts the Makefile coverage gate and the `ci.yml` gate never drift apart again (the 52 → 70 drift fixed inside Q14-01 was found by hand) | Local scope done; server-side enforcement unavailable (private repo on a free plan — `branches/main/protection` and `rulesets` both 403). Degraded to documented convention + installed hook, recorded in `docs/ci-workflows.md` |
| Q15-02 | Every backend test file runs standalone | All 183 non-integration files pass individually; the 8 `sys.path` cases go through a shared bootstrap (extend `backend/tests/_paths.py` or a `tests/__init__.py`), the root conftest's `app.api.deps` stub gains `assert_project_access` / `require_project_access`, and `test_conftest_stubs.py` imports its target without requiring an ambient `tests` package; a CI step runs the per-file sweep so the property cannot regress | Done — 191 files pass individually; `make test-backend-standalone` + a CI sweep step guard it |
| Q15-03 | Windows CI job | `ci.yml` gains a `windows-latest` backend pytest job (Python 3.12, no Docker services — the unit suite already stubs infra); the job is required by Q15-01's protection set; `docs/ci-workflows.md` documents scope and the deliberate exclusions (integration/E2E stay Linux-only) | Done — `backend-test-windows` job added; the "required check" half is impossible on this plan and is recorded as such |
| Q15-04 | Frontend `views/system` mount coverage | Mount tests (@vue/test-utils, Q14-03 convention) for the largest system pages — `DatasetLibrary`, `ReportCenterView`, `StorageManagementView`, `NotificationList`, `BugTrackerList`, `MockRulesView` — taking the `views/system` directory from 2.54% to >= 35% and frontend statements to **>= 28%**; Vitest gates raised to the achieved floor | Not started |
| Q15-05 | Backend maintenance/worker coverage + gate realignment | Behavioral seams for `worker/tasks_performance.py` (0%), `worker/tasks_db_backup.py`, `services/ai_healing_stats.py`, `services/dashboard_alerts.py`, and `services/mobile_special/aggregator.py`, following the Q13/Q14 fake-boundary convention; backend TOTAL >= 86% and the CI gate raised 70 -> 82 so it tracks reality again | Done — five named modules plus four routers; TOTAL 86.04% on Python 3.12 (85.55% on 3.14), gate raised 70 -> 82 |
| Q15-06 | Resolve the chartTheme load sensitivity | Either give `chartTheme.spec.ts` a timeout proportional to its dynamic import (or drop the dynamic import), or mark it `flaky` with an entry in `docs/flaky-governance.md` recording cause, evidence and exit criteria per policy. A one-line "raise testTimeout globally" change is explicitly not acceptable — the item must state which of the two paths was chosen and why | Done — mocked the three remaining echarts entry points; in-test time 196-289ms -> 12-13ms, not registered flaky, global timeout untouched |
| Q15-07 | Q14 acceptance summary | `docs/q14-acceptance-summary.md` in the Q13 format: the six local Q14 items, the coverage arc (backend 74% -> 82.73%, frontend 8.51% -> 21.48%), the Q14-00 carry-forward, and the gate-enforcement failure this roadmap opens with — including the two production-affecting defects it let through (`run_retention` mypy errors, the Windows-only test break) | Not started |

## Execution Order

1. **Q15-01 first, alone.** Every later item's evidence is only worth what the gates
   are worth. Until required checks actually block a merge, a green local run proves
   nothing about `main`. This is also the cheapest item in the quarter.
2. **Q15-02 and Q15-03 next, in that order.** The Windows job will re-run the whole
   backend suite in a fresh process on a different OS; landing the standalone-runnability
   fixes first means Windows failures are genuinely platform failures rather than
   order-dependence noise. Both then become required checks under Q15-01.
3. **Q15-06 alongside Q15-02.** It is a single-file decision and it belongs with the
   test-robustness thread; leaving a known load-sensitive test in place while adding a
   second CI runner invites it to fail on the new job first.
4. **Q15-04 and Q15-05 in parallel** (frontend `views/system` vs backend
   worker/maintenance modules, no file overlap), both building directly on the Q14
   conventions. Q15-05 carries the gate realignment 70 -> 82, which should land only
   after Q15-01 makes gate changes meaningful.
5. **Q15-07 last**, so it reports stable numbers, as Q14-06 did for Q13.
6. **Q15-00 interrupts anything** the moment a scraped deployment and a physical Android
   device are available. The 7/14-day capture windows are calendar time, not work, and
   they have now slipped through three quarters.

## Current Residual Risks

- Q12 still cannot be declared fully accepted, and this is the third consecutive quarter
  carrying that item. If environment access is not going to materialise, the honest move
  is to re-scope Q12-05 (for example, accept a shorter window or a documented
  non-production substitute) rather than carry it into Q16 — that decision is outside
  local control and should be made explicitly rather than by default.
- Branch protection may not be configurable on the repository's current plan. If so,
  Q15-01 degrades to a documented convention plus an installed local hook, which is
  weaker: it prevents the accident, not the deliberate bypass. The item should say so
  plainly rather than claim enforcement it does not have.
- Raising the backend gate 70 -> 82 narrows headroom to ~4 points. That is intentional
  (a gate 12 points below reality detects nothing) but it will make unrelated PRs fail
  on coverage more often; expect friction and be prepared to defend or tune it.
- A Windows CI job doubles backend suite wall-clock in CI and will surface latent
  platform assumptions beyond tests (path handling in `scripts/`, `bash`-invoking code
  paths). Some findings may be out of Q15 scope; triage them into Q16 rather than
  expanding this quarter.
- `views/system` mount tests will hit the same ceiling Q13-03 documented: helper
  extraction yields ~+0.07pt/slice versus ~+1pt/mount-test. The 28% target assumes the
  mount-test technique holds for pages heavier than the Q14 workbench views; if
  `DatasetLibrary.vue` (727 lines) resists mounting, re-scope the item to fewer pages
  rather than reverting to helper extraction.

## Next Action

Confirm whether `main` has required status checks (authenticated `gh api
repos/2653533859/ATP/branches/main/protection`, or the repository settings UI). That
answer determines whether Q15-01 is a configuration change or a documentation-plus-hook
compromise, and it is the precondition for every other item in the quarter.

## Execution Log (2026-08-01)

What actually happened against the plan above, including the two places the plan
turned out to be wrong.

### Landed

- **Q15-01 (local scope).** Branch protection is **not configurable on this
  plan** — `gh api repos/2653533859/ATP/branches/main/protection` and
  `.../rulesets` both return 403 (`Upgrade to GitHub Pro or make this repository
  public`), and the repo is private under a personal account. The residual risk
  this roadmap listed therefore materialised: Q15-01 degrades to a documented
  convention plus an installed local hook, recorded with its limits in
  `docs/ci-workflows.md`. What did land: the mypy hook no longer depends on the
  ambient `PATH` python; `make setup` installs `requirements-dev.txt` and runs
  `pre-commit install` (non-fatal, after `npm ci`); and
  `backend/tests/test_quality_gate_consistency.py` now fails on any drift
  between the Makefile, `ci.yml`, `.pre-commit-config.yaml` and the CI doc.
- **Q15-02.** All 191 non-integration files pass individually. The 10 failures
  had a single root cause chain: the root conftest never put `backend/` on
  `sys.path` (144 files each carried their own `sys.path.insert`, and the ones
  that forgot relied on another file running first). Fixing that in the conftest
  also fixed `test_conftest_stubs.py`'s `No module named 'tests'`, which needs
  `tests` to resolve as a namespace package. The `app.api.deps` stub gained
  `assert_project_access` / `require_project_access`.
  `make test-backend-standalone` and a CI step guard the property.
- **Q15-03.** `backend-test-windows` runs the unit suite on `windows-latest`.
  The "required check" half of the acceptance criteria is impossible here (see
  Q15-01) and is written down as unmet rather than quietly dropped.
- **Q15-05.** The five named modules went 0/9/26/44/56% to 100/95/98/93/98%.
  Four routers were added on top to reach the TOTAL target:
  `api/v1/auth.py` and `api/v1/scripts.py` were both at **0%**, plus
  `api/v1/dashboard_alerts.py` and `api/v1/performance.py`. TOTAL is 86.04% on
  Python 3.12 and the gate moved 70 -> 82.
- **Q15-06.** Neither of the two paths the plan offered was taken verbatim.
  The load sensitivity was not external timing: the spec mocked `echarts/core`
  but left `echarts/charts`, `echarts/components` and `echarts/renderers` real,
  so every dynamic import re-transformed the echarts subgraph for modules no
  assertion touches. Mocking those three cut in-test time from ~196-289ms to
  ~12-13ms (three cold runs), restoring roughly a 400x margin against the
  5000ms default. Not registered as flaky (rule 2 of
  `docs/flaky-governance.md` does not apply) and the global `testTimeout` was
  left alone.

### Corrections to this plan's inputs

- **The 82.73% / 13962-statement input is interpreter-specific.** The same
  command reads 13962 statements on Python 3.12 and 13367 on 3.14, about 0.5
  points apart. The gate was therefore set against the 3.12 number and verified
  against 3.14. Details in `docs/coverage-baseline-2026-q13.md`.
- **Two gate defects this plan did not list.** The `.pre-commit-config.yaml`
  mypy hook and `ci.yml`'s `backend-lint` job both installed only
  `requirements-dev.txt`, so mypy could not see SQLAlchemy's real signatures:
  `d116359^`'s `run_retention.py` reports 8 errors that way versus 12 in a full
  environment — and the 4 missing `not_in()` `arg-type` errors are exactly the
  batch that motivated this quarter. Both now install the runtime requirements.
  Separately, ruff's script list existed only in the Makefile, so
  `scripts/pytest-standalone-sweep.py` — which CI executes — was not linted by
  CI or the hook.

### Still open

- **Q15-04** (frontend `views/system` mount coverage) — not started.
- **Q15-07** (Q14 acceptance summary) — not started; the plan puts it last so it
  reports stable numbers.
- **Q15-00** — still blocked on a scraped deployment and a physical device.
