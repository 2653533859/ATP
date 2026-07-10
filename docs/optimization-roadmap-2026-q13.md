# ATP Optimization Roadmap 2026 Q13

## Goal

Convert the Q12 quality foundation into execution-path confidence. Q13 targets the two largest measured risk pools — the untested worker execution chain (backend 53% total, with `worker/tasks.py` and all nine executors nearly uncovered) and the zero-coverage frontend workbench views — while carrying the Q12-05 environment-dependent captures to completion and turning one deferred product capability (AI healing apply-loop) into a shippable slice.

Planning inputs (measured 2026-07-10):

- Backend coverage TOTAL 53% (13327 statements, 5731 missed). Largest gaps: `worker/tasks.py` (362 missed), the nine executors together (~1450 missed), `services/bug_reporter.py` (261), `api/v1/exports.py` (197), `services/ai_healing.py` (185), `services/failure_diagnosis.py` (124), `api/v1/mobile_special.py` (143).
- Frontend statements 4.37%; the entire workbench tier is zero-covered: `CaseList.vue` (587 uncovered statements), `RunDetail.vue` (539), `SuiteList.vue` (537), `DashboardView.vue` (513), `CaseFormDrawer.vue` (449), `PlanList.vue` (379).
- `ant-design` remains the largest chunk (1246.41 kB) after Q12-04 on-demand registration; the bundle-decision doc names route-family isolation as the next lever.
- AI healing iter5 phase 1 (structured suggestion contract + parameter whitelist) is live; phase 2 (human-reviewed apply + regression verification) exists only as design.
- Q12-05 SLO history and physical-device rehearsal formats are frozen in `docs/q12-external-readiness-evidence.md`, blocked on environment access.

## Work Items

| ID | Work item | Acceptance criteria | Status |
| --- | --- | --- | --- |
| Q13-00 | Close Q12-05 captures and publish Q12 acceptance | When environment access arrives: dated `docs/slo-history-*.md` and `docs/android-device-rehearsal-*.md` per the frozen spec, then `docs/q12-acceptance-summary.md` | Blocked on environment (may land any time during Q13) |
| Q13-01 | Backend execution-chain coverage | Unit seams for `worker/tasks.py` dispatch/finalization and per-executor request-build/assert/extract logic; backend TOTAL >= 60% with the CI gate raised 52% -> 56% | Complete (TOTAL 60.03%, gate 56%, `924 passed`; HTTP-family seams fixed a live protobuf 5 break in grpc_executor) |
| Q13-02 | Backend service/API coverage | Behavioral tests for `bug_reporter`, `ai_healing`, `failure_diagnosis`, `exports`, `mobile_special` API; each records before/after coverage in the baseline doc | Complete (bug_reporter 95% / failure_diagnosis 97% / ai_healing 89% / exports 92% / mobile_special 91%; TOTAL 66.98%, gate 62%; fixed a live create_task 500) |
| Q13-03 | Frontend workbench behavioral coverage | Four slices (CaseList, RunDetail, SuiteList, DashboardView) extracting testable helpers per the proven Q12-02 pattern; frontend statements >= 8% with gates ratcheted per the 0.25pt headroom policy | Five slices done (four workbench + CaseFormDrawer): statements 4.38%->6.33%, branches past 8%, `74 passed`; one more form-drawer slice (PlanForm) reaches the 8% statement target |
| Q13-04 | Ant Design route-level chunk evidence | Route-family sharing analysis captured in `docs/frontend-bundle-decision.md`; go/no-go decision on route isolation, implemented only if measured transfer saving >= 15% on a first-paint route | Planned |
| Q13-05 | AI healing apply-loop slice (iter5 phase 2) | Human-approved suggestion can be applied to a case snapshot and verified by an automatic re-run, guarded by the existing whitelist; audit trail recorded; feature-flagged off by default | Planned |
| Q13-06 | Dependency hygiene | `npm approve-scripts` allowlist reviewed and committed; quarterly refresh of backend/frontend pins with zero new deprecations or audit findings | Planned |

## Execution Order

1. Q13-01 and Q13-03 start first and run in parallel (backend vs frontend, no file overlap); both are pure local work.
2. Q13-02 follows Q13-01 once the executor seams establish the mocking conventions for external I/O (httpx, Playwright, ADB, MinIO).
3. Q13-04 is a short evidence-then-decide task; schedule it between coverage slices.
4. Q13-05 starts after Q13-02 covers `services/ai_healing.py`, so the apply-loop lands on tested ground.
5. Q13-00 interrupts anything the moment environment access is granted — the capture windows (7/14 days) are the long pole for closing Q12.
6. Q13-06 runs as a background chore, first pass immediately.

## Current Residual Risks

- The execution chain (dispatch + executors) is the platform's core value path and its least-tested code; regressions there surface only in live runs today.
- Frontend workbench views mutate state through large untyped-until-Q12 templates; behavioral coverage is the remaining guard the type system cannot provide.
- The ant-design chunk stays within its threshold but dominates first-paint transfer (374.7 kB gzip of 510.1 kB total on /login).
- AI healing phase 2 writes to cases; without the Q13-05 flag-and-audit design it stays a manual copy-paste flow.
- Q12 cannot be declared fully accepted until the two environment-dependent captures execute.

## Next Action

Q13-03 is at frontend statements 6.33% (branches already past 8%) after the four workbench slices plus CaseFormDrawer. One more form-drawer slice — the PlanList create/edit config helpers — should carry statements over the 8% acceptance line and close Q13-03. Q13-04 (Ant Design route-level chunk evidence), Q13-05 (AI healing apply-loop, now unblocked), and Q13-06 (dependency hygiene) remain; Q13-00 (Q12-05 captures) interrupts on environment access.
