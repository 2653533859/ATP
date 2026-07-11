# ATP Optimization Roadmap 2026 Q14

## Goal

Consolidate the Q13 coverage surge into durable regression protection and clear the
long-standing engineering backlog. Q14 has no new product direction. It formalizes the
three threads that Q13 left open: (1) the coverage extension that has been running as
unscheduled follow-on work (backend TOTAL 53% -> 74% across Q13) now gets an explicit
target and gate policy; (2) the frontend workbench views, still 0% at the component
level, get mount-test coverage — the technique Q13-03 proved moves +1pt/test vs
+0.07pt/helper-slice; (3) two documented leftovers (per-project retention real cleanup,
gitleaks pre-commit hook) and the Q13 acceptance summary are brought to done. Q13-00
(the environment-blocked Q12-05 captures) carries forward and interrupts the moment a
scraped deployment and a physical device are available.

## Planning inputs (measured 2026-07-11)

- Backend coverage TOTAL **74%** (13331 statements), `1154 passed`, CI gate at **66%**.
  Largest remaining gaps are the Android execution family and the ADB layer, plus the
  two browser/device low-code executors partially covered in Q13:
  - `worker/executors/android_executor.py` ~23% (async `create_subprocess_exec`
    orchestration is the heavy, still-uncovered path)
  - `worker/executors/android_stability_executor.py` ~23%
  - `worker/executors/android_fluency_executor.py` ~26%
  - `worker/executors/android_perf_executor.py` (partial)
  - `worker/executors/web_lowcode_executor.py` 51%
  - `worker/executors/android_lowcode_executor.py` 53%
  - `services/adb_service.py` ~27%
  - Mid-covered API routers not yet in a coverage slice (suites / cases / runs /
    notifications / datasets) — re-measure and data-drive the pick.
- Frontend coverage: statements **8.51%**, branches **9.93%**, functions **6.53%**,
  lines **8.44%** (`86 passed`); gates 8.2 / 9.6 / 6.2 / 8.15. The six workbench views
  are still 0% at the component level (only their extracted helpers are tested):
  `CaseList.vue`, `RunDetail.vue` (1181 lines), `SuiteList.vue` (1215 lines),
  `DashboardView.vue`, `PlanList.vue`, plus every `views/system` page except
  `EnvironmentList.vue`.
- Per-project run retention: `Project.run_retention_days_override`,
  `resolve_project_retention`, and `preview_old_runs_by_project` exist
  (`backend/app/services/run_retention.py`), but the real cleanup
  (`execute_old_runs_cleanup`, line 236; Celery `cleanup_old_completed_runs`;
  `POST /admin/runs/retention/run`) still deletes by the **global** cutoff only. The
  per-project preview itself punts on test/mobile runs (line 342 note).
- Gitleaks pre-commit: CI runs `gitleaks/gitleaks-action@v2`
  (`.github/workflows/security.yml`) and `.gitleaks.toml` already holds the allowlist,
  but `.pre-commit-config.yaml` has no local gitleaks hook — the Q10 Phase 4 item that
  stayed `[~]` pending a local-install decision.
- Q13 shipped six roadmap items plus a large coverage extension but has no
  `docs/q13-acceptance-summary.md` (Q10/Q11 both have one).

## Work Items

| ID | Work item | Acceptance criteria | Status |
| --- | --- | --- | --- |
| Q14-00 | Close Q12-05 captures + publish Q12/Q13 acceptance | When environment access arrives: dated `docs/slo-history-*.md` and `docs/android-device-rehearsal-*.md` per the frozen spec, then `docs/q12-acceptance-summary.md` | Blocked on environment (carried from Q13-00) |
| Q14-01 | Backend Android/ADB executor coverage | Behavioral seams for `android_executor`, `android_stability/fluency/perf_executor`, `web_lowcode_executor`, and `services/adb_service.py` following the Q13 fake-transport convention; backend TOTAL >= 78%, CI gate raised 66% -> 70% | Complete (android family 82-93%, adb_service 97%, web_lowcode 97%, android_lowcode 98%; TOTAL 81%, `1267 passed`, gate 70 in CI + Makefile) |
| Q14-02 | Backend API-router coverage sweep | Data-driven pick of the largest mid-covered routers (suites / cases / runs / notifications / datasets); each records before/after in the baseline doc; TOTAL >= 80% | Not started |
| Q14-03 | Frontend workbench mount tests | Mount tests (@vue/test-utils) for the highest-traffic workbench views (CaseList, RunDetail, SuiteList, DashboardView, PlanList) reaching frontend statements >= 12% | Not started |
| Q14-04 | Per-project retention real cleanup | `execute_old_runs_cleanup` / Celery task / admin run honor per-project overrides for all four run types (plan/suite/test/mobile), close the line-342 test/mobile preview gap, add regression tests | Not started |
| Q14-05 | Gitleaks pre-commit hook | Local gitleaks hook added to `.pre-commit-config.yaml` reusing `.gitleaks.toml`; documented install path; Q10 Phase 4 item flips `[~]` -> `[x]` | Not started |
| Q14-06 | Q13 acceptance summary | `docs/q13-acceptance-summary.md` summarizing the six Q13 items, the coverage extension (53% -> 74%), the three production bugs found+fixed, and the frontend 4.38% -> 8.51% arc | Not started |

## Execution Order

1. Q14-01 and Q14-03 start first and run in parallel (backend executors vs frontend
   mount tests, no file overlap) — both pure local work, both build directly on Q13
   conventions.
2. Q14-04 (retention cleanup) is a real behavior change, not just coverage; schedule it
   early while the retention service is fresh, and let its new tests count toward the
   Q14-02 sweep.
3. Q14-05 (gitleaks hook) is a short chore — do it in one pass alongside Q14-04.
4. Q14-02 follows Q14-01 once the executor family is closed and the remaining gaps are
   API routers; re-measure coverage first to data-drive the pick.
5. Q14-06 (Q13 acceptance) closes once Q14-01..05 land, so it reports a stable coverage
   number.
6. Q14-00 interrupts anything the moment environment access is granted — the 7/14-day
   capture windows are the long pole for closing Q12.

## Current Residual Risks

- The Android execution family (perf/stability/fluency + ADB service) is the last
  large near-blind spot in the worker; its async subprocess orchestration is the
  heaviest seam left and regressions there surface only on real devices.
- Frontend workbench views mutate state through 1000+ line templates; helper tests
  cover the extracted logic but not the reactive wiring — mount tests are the only
  guard for that layer.
- Per-project retention is a latent correctness gap: operators can set an override that
  silently does nothing on real cleanup, only appearing to work in the preview.
- Q12 cannot be declared fully accepted until the two environment-dependent captures
  execute; that remains outside local control.

## Next Action

Start Q14-01 (Android/ADB executor seams) and Q14-03 (workbench mount tests) in
parallel. Q14-01 extends the established fake-transport convention
(`docs/coverage-baseline-2026-q13.md`) to the ADB shell boundary; Q14-03 extends the
ApkList/DeviceList mount-test pattern to the large workbench views. Re-run backend and
frontend coverage first to refresh the exact per-module numbers this roadmap estimated
from the Q13 records.
