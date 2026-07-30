# Q14 Completion Audit

> Date: 2026-07-12
> Scope: `docs/optimization-roadmap-2026-q14.md`
> Verdict: local Q14 work is complete; full Q14 completion is pending Q14-00 external evidence.

This audit records the requirement-by-requirement evidence for closing Q14. It
does not replace the Q12 external evidence package; it explains why Q14 can be
considered locally closed while Q14-00 remains open until real environment
captures exist.

## Evidence Summary

| Item | Required evidence | Current evidence | Status |
| --- | --- | --- | --- |
| Q14-00 | Dated `docs/slo-history-*.md`, dated `docs/android-device-rehearsal-*.md`, then `docs/q12-acceptance-summary.md` passing `make validate-q12-evidence` | Frozen spec in `docs/q12-external-readiness-evidence.md`; templates in `docs/templates/`; automated collector in `scripts/collect-q12-evidence.py`; scaffold helper in `scripts/scaffold-q12-evidence.py`; validator in `scripts/validate-q12-evidence.py`; Make targets `collect-q12-evidence`, `scaffold-q12-evidence`, and `validate-q12-evidence` | Blocked on external production-like SLO history and physical Android device rehearsal |
| Q14-01 | Android/ADB executor coverage with backend TOTAL >= 78% and gate 70 | `docs/coverage-baseline-2026-q13.md` records Q14-01 at `1267 passed`, backend TOTAL `81%`, gate `70`; latest full backend run is `1327 passed`, TOTAL `82.19%`, gate `70` | Complete |
| Q14-02 | API-router sweep with backend TOTAL >= 80% and before/after baseline record | `docs/coverage-baseline-2026-q13.md` records API-router sweep closeout at `1310 passed`, TOTAL `82.20%`; latest full backend run remains above gate at `82.19%` | Complete |
| Q14-03 | Mount tests for CaseList, RunDetail, SuiteList, DashboardView, PlanList and frontend statements >= 12% | Five workbench spec files exist under `frontend/src/views/**`; `docs/coverage-baseline-2026-q13.md` records `102 passed`, statements `21.48%`, gate `20.5` | Complete |
| Q14-04 | Retention cleanup honors per-project overrides for plan/suite/test/mobile and preview includes test/mobile | `docs/optimization-roadmap-2026-q14.md` records run retention behavior complete with service coverage `78 -> 90%` | Complete |
| Q14-05 | Local gitleaks pre-commit hook reusing `.gitleaks.toml` | `docs/optimization-roadmap-2026-q14.md` and `Task.md` record the official gitleaks pre-commit hook v8.24.3 | Complete |
| Q14-06 | `docs/q13-acceptance-summary.md` published | `docs/q13-acceptance-summary.md` exists and records Q13 local completion plus Q13-00 carry-forward | Complete |

## Latest Verification

The current local proof was refreshed on 2026-07-29 with:

```bash
backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=term-missing:skip-covered --cov-report=xml --cov-fail-under=70
npm --prefix frontend run test:coverage
backend/.venv/bin/python -m pytest backend/tests/worker/test_q12_external_readiness.py backend/tests/worker/test_q12_evidence_validator.py backend/tests/worker/test_q12_evidence_collector.py -q
backend/.venv/bin/python -m py_compile scripts/collect-q12-evidence.py
make lint PYTHON=backend/.venv/bin/python
git diff --check
```

Results:

- Backend: `1327 passed`, TOTAL `82.19%`, coverage gate `70` passed. The total
  fluctuates between `82.19%` and `82.20%` across runs (one line of
  `backend/app` is covered nondeterministically); the conservative value is
  recorded here.
- Frontend: `25 files / 102 tests passed`, statements `21.48%`, branches
  `18.48%`, functions `17.44%`, lines `22%`.
- Q12 evidence tooling: `20 passed`, including the new collector regressions;
  the collector smoke path writes all three evidence documents plus fixtures and
  passes `validate_all(...) == []`. The collector regressions pin six
  invariants: P95 latency reports the daily peak (not the trough) so spikes raise
  breaches, a window with no Prometheus samples is recorded as a data gap that
  keeps alerting and the release gate deferred, pre-existing evidence aborts
  the run before the expensive device rehearsal starts, `increase(...[1d])`
  samples are filed under the day they measure rather than the day after,
  integer counts keep their trailing zeros (`200` must not render as `2`), and
  API credentials come only from `ATP_USERNAME`/`ATP_PASSWORD` so the host's
  `USERNAME`/`PASSWORD` cannot authenticate the collector.
- Lint and whitespace checks passed for the changed Q14/Q12 tooling surface.

## Completion Decision

Q14 cannot be marked fully complete until Q14-00 has real evidence:

1. A production or production-like Prometheus SLO window with day-7 and day-14
   records in `docs/slo-history-<start>-<end>.md`.
2. A physical Android device rehearsal in
   `docs/android-device-rehearsal-<date>.md`.
3. `docs/q12-acceptance-summary.md` linking both records.
4. `make collect-q12-evidence` used to collect and render live Prometheus/API/ADB
   artifacts automatically, or `make scaffold-q12-evidence` used only for
   template drafts.
5. `make validate-q12-evidence` passing against those three files.

Until those files exist and pass validation, the accurate status is: Q14 local
work complete, full Q14 blocked on external environment access.
