# Q14 Acceptance Summary

> Date: 2026-08-06
> Status: all six locally executable Q14 items are accepted; Q14-00 remains open because its production-like SLO and physical Android evidence requires external environment access.

## Scope

Q14 consolidated the coverage work left open by Q13, hardened the retention
cleanup behavior, added local secret scanning, and published the Q13 acceptance
summary. The external Q12-05 evidence package was deliberately carried forward
as Q14-00 rather than being represented by local fixtures.

## Accepted Outcomes

### Android and ADB execution coverage (Q14-01)

- Android executor paths, the low-code Android/Web families, and the ADB service
  have behavioral coverage at the boundaries that can be isolated without a
  device.
- Backend coverage crossed the Q14 gate: the audit records `1267 passed` and
  `81%` at the item close, with the gate raised from `66%` to `70%`.
- The latest local verification remains above that gate; the detailed evidence
  is in `docs/q14-completion-audit.md` and `docs/coverage-baseline-2026-q13.md`.

### API router sweep (Q14-02)

- The remaining high-value router gaps, including suites, notifications,
  device/healing-prompt statistics, and related permission branches, were
  covered with request-level behavior tests.
- The closeout baseline reached `1310 passed` and `82.20%` backend coverage.

### Workbench mount coverage (Q14-03)

- CaseList, RunDetail, SuiteList, DashboardView, and PlanList now have
  component-level mount coverage for their primary initialization and user
  interaction paths.
- Frontend coverage reached `102 passed` and `21.48%` statements, raising the
  statements gate to `20.5%`.

### Project-scoped retention cleanup (Q14-04)

- Cleanup honors per-project retention overrides for plan, suite, test, and
  mobile runs while preserving the global retention fallback for projects that
  do not override it.
- Preview output includes the same test and mobile categories as execution;
  the `run_retention` service moved from `78%` to `90%` coverage.

### Local secret scanning (Q14-05)

- The official Gitleaks `v8.24.3` pre-commit hook is configured and reuses the
  repository `.gitleaks.toml` allowlist.
- CI continues to use the Gitleaks action; local and CI scanning therefore share
  the same repository policy while keeping the local hook explicitly documented.

### Q13 acceptance record (Q14-06)

- `docs/q13-acceptance-summary.md` is published and records the six Q13 local
  outcomes, coverage growth, frontend bundle decision, dependency hygiene, and
  the production defects found by coverage work.

## Coverage Arc and Gate Finding

| Metric | Q14 starting baseline | Q14 closeout baseline |
| --- | ---: | ---: |
| Backend TOTAL | `74%` | `82.73%` |
| Frontend statements | `8.51%` | `21.48%` |
| Backend CI gate | `66%` | `70%` |
| Frontend statements gate | `8.2%` | `20.5%` |

Q14 also exposed why declared gates are not sufficient when the hosting plan
does not enforce required checks. A `run_retention` mypy defect and a
Windows-only test path defect both reached `main` while CI was green. Q15
therefore carries the enforcement problem forward: local hooks and consistency
contracts are complete, but server-side required checks remain unavailable on
the current private free-plan repository.

## Carry-Forward: Q14-00

Full Q14 acceptance still requires real evidence, not repository fixtures:

1. A production or production-like Prometheus window with day-7 and day-14 SLO
   records in `docs/slo-history-<start>-<end>.md`.
2. A physical Android rehearsal in `docs/android-device-rehearsal-<date>.md`.
3. `docs/q12-acceptance-summary.md` linking both records and passing
   `make validate-q12-evidence`.
4. Evidence captured with `make collect-q12-evidence`, or a clearly marked
   scaffold used only as a draft.

The collector, scaffold, and validator are ready. Until a continuously
scraped deployment and a physical device are available, the accurate decision
is: **Q14 local work accepted; Q14-00 blocked on external environment access**.

## Source Evidence

- `docs/q14-completion-audit.md`
- `docs/coverage-baseline-2026-q13.md`
- `docs/q12-external-readiness-evidence.md`
- `docs/optimization-roadmap-2026-q14.md`
