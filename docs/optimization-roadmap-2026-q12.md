# ATP Optimization Roadmap 2026 Q12

## Goal

Close the residual quality risks left after Q11 acceptance. Q12 prioritizes clean test signals, measurable coverage growth, dependency maintenance, and production-like evidence for the remaining infrastructure paths.

## Work Items

| ID | Work item | Acceptance criteria | Status |
| --- | --- | --- | --- |
| Q12-00 | Eliminate pytest collection noise | No `PytestCollectionWarning`; the full backend suite treats this warning as an error | Complete (`841 passed` after review cleanup) |
| Q12-01 | Refresh coverage baselines | Backend `53.46%` with a `52%` gate; frontend statements `3.66%` with initial multi-metric gates and CI artifact | Complete |
| Q12-02 | Raise frontend critical-flow coverage | Authentication, case execution, scheduling, and reporting slices complete; `46 passed` after review cleanup | Complete |
| Q12-03 | Retire dependency deprecations | Resolve or explicitly time-box vue-i18n and transitive glob deprecation notices | Complete (zero `npm warn deprecated` on clean install) |
| Q12-04 | Validate frontend chunk boundaries | Capture route-level load evidence and decide whether Ant Design on-demand imports are warranted | Planned (follow-up trigger fired: ant-design chunk 1502.45 kB > 1500 kB) |
| Q12-05 | Complete external readiness evidence | Record production-like SLO history and a physical Android device execution rehearsal | Planned |

## Execution Order

1. Finish Q12-00 so later regression output is trustworthy.
2. Establish Q12-01 baselines before changing test volume or thresholds.
3. Execute Q12-02 and Q12-03 in parallel where their files do not overlap.
4. Close Q12-04 and Q12-05 with measured evidence, then publish the Q12 acceptance summary.

## Current Residual Risks

- Backend collection previously emitted 41 warnings from imported application classes named `Test*`; Q12-00 silenced them centrally (a `pytest_pycollect_makeitem` hook in `backend/tests/conftest.py` skips `Test*` classes imported from `app.*`) with a strict pytest warning gate, so tests import application classes by their real names.
- Frontend full-source coverage is below the desired confidence level for critical workflows.
- ~~vue-i18n and transitive glob packages emit deprecation notices during dependency operations.~~ Resolved by Q12-03: vue-i18n upgraded to `11.4.6` (Composition API mode unaffected), transitive glob forced to `13.0.6` via npm override (`@vue/test-utils > js-beautify` only uses glob in its CLI path).
- The Ant Design vendor chunk crossed the 1500 kB warning threshold (1502.45 kB) after the vue-i18n dependency-graph reshuffle; per `docs/frontend-bundle-decision.md` the threshold stays at 1500 kB and Q12-04 owns the on-demand import decision.
- Physical Android device data-plane evidence and long-window production SLO evidence remain environment-dependent.

## Next Action

Q12-04 is next, and its follow-up trigger has already fired: the ant-design chunk reached 1502.45 kB (> 1500 kB) after the Q12-03 vue-i18n upgrade reshuffled the module graph. Capture route-level load evidence, then decide between automatic on-demand component resolution and a tested explicit registration layer as recorded in `docs/frontend-bundle-decision.md`.
