# Q13 Acceptance Summary

> Date: 2026-07-11
> Status: all six locally-executable roadmap items complete; Q13-00 (Q12-05 production SLO history + physical-device rehearsal) carries into Q14-00, blocked on external environment access.

## Scope

Q13 converted the Q12 quality foundation into execution-path confidence: behavioral coverage for the worker execution chain and service/API layer, frontend workbench testability, bundle evidence, the AI-healing apply loop, and dependency hygiene — plus a large unscheduled coverage extension that Q14 later formalized.

Six of the seven items in `docs/optimization-roadmap-2026-q13.md` are complete; the seventh is environment-blocked by design.

## Accepted Outcomes

### Backend Execution-Chain Coverage (Q13-01)

- Unit seams for `worker/tasks.py` dispatch/finalization (35% -> 86%) and all nine executors, faking only the transport/driver boundary (httpx, Playwright, ADB shell, MinIO, Redis).
- Backend TOTAL 53% -> 60.03% inside the item; CI gate raised 52% -> 56%.
- The HTTP-family slice exposed and fixed a live production break: `message_factory.GetPrototype` removed in protobuf 5+ had the grpc executor failing on every run.

### Backend Service/API Coverage (Q13-02)

- `bug_reporter` 95%, `failure_diagnosis` 97%, `ai_healing` 89%, `exports` 92%, `mobile_special` API 91%; TOTAL 66.98%, gate 62%.
- Exposed and fixed a second live break: mobile-special `create_task` 500'd on every call (`created_by` duplicated between schema dump and explicit kwarg).

### Frontend Workbench Coverage (Q13-03)

- Six helper-extraction slices (CaseList, RunDetail, SuiteList, DashboardView, CaseFormDrawer, PlanList cron) took statements 4.38% -> 6.40%; a mount-test slice (ApkList + DeviceList) crossed the acceptance line at **8.51%** (`86 passed`).
- Established the finding Q14 builds on: mount tests move ~+1pt each vs +0.07pt per helper slice.

### Bundle Evidence (Q13-04)

- Route-family analysis produced a GO decision: the antd monolith chunk was dropped, /login first-paint transfer 510 -> 336 kB gzip (-34%), chunk warning limit tightened 1500 -> 600 kB.

### AI Healing Apply Loop (Q13-05)

- Human-approved suggestions can be applied to a case snapshot and verified by an automatic re-run, guarded by the existing parameter whitelist and an `AI_HEALING_APPLY_ENABLED` flag (off by default), with an audit trail.
- Exposed and fixed a third latent 500: `ProjectRole.engineer` did not exist in the role enum used by the endpoint.

### Dependency Hygiene (Q13-06)

- npm `allowScripts` allowlist (core-js / fsevents / vue-demi) reviewed and committed; `npm ci` clean, audits at 0 vulnerabilities; policy recorded in `docs/dependency-hygiene.md` with a contract test.

### Coverage Extension (unscheduled, later formalized as Q14-01/02)

Follow-on slices within the Q13 window took backend TOTAL to 74-75% and closed the largest blind spots: environments API 0 -> 100%, WebSocket endpoint 0 -> 89%, mobile-special collectors/dispatch, projects / bug-trackers / plans APIs, and the global-variables API 24 -> 98% — the last exposing and fixing a fourth live break (`create_variable` 500'd on every call: `value_encrypted` duplicated between the model_dump spread and an explicit kwarg; the variable library could not create any variable).

## Production Bugs Found And Fixed By Coverage Work

1. grpc executor: protobuf 5+ removed `message_factory.GetPrototype` — every grpc run failed.
2. mobile-special `create_task`: duplicate `created_by` kwarg — every create 500'd.
3. ai_healing apply endpoint: nonexistent `ProjectRole.engineer` — 500 on access.
4. global-variables `create_variable`: duplicate `value_encrypted` kwarg — every create 500'd.

All four were proven by a failing test first, then fixed; the shared kwarg-duplication class was audited repo-wide.

## Metrics

| Metric | Q13 start | Q13 end |
| --- | --- | --- |
| Backend TOTAL (branch coverage) | 53% (844 passed) | 74-75% (1154-1168 passed) |
| Backend CI gate | 52% | 66% |
| Frontend statements | 4.38% (46 passed) | 8.51% (86 passed) |
| /login first-paint transfer | 510 kB gzip | 336 kB gzip |

Per-slice before/after evidence: `docs/coverage-baseline-2026-q13.md`.

## Carried Forward

- Q13-00 -> Q14-00: production SLO 7/14-day history and Android physical-device rehearsal, frozen in `docs/q12-external-readiness-evidence.md`, still blocked on environment access.
- The coverage extension's momentum was formalized as Q14-01 (Android/ADB executor family) and Q14-02 (API-router sweep) with explicit gates.
