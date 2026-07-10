# ATP Q11 Optimization Roadmap

> Created: 2026-07-08
> Purpose: Continue after Q10 quality closure with release packaging, production calibration, coverage growth, and operational hardening.

## Current Baseline

Q10 is complete:

- Backend lint / format / mypy / coverage gates are in place.
- Frontend Vitest and Playwright E2E baselines are in place.
- Bandit, pip-audit, npm audit, Gitleaks, Trivy, and Dependabot are documented and wired.
- Real-infra integration and suite / plan frontend E2E have expanded coverage.
- SLO thin slice and flaky governance are documented.
- `docs/q10-acceptance-summary.md` records the acceptance evidence.

## Priority Principles

1. Keep the current large diff reviewable: separate formatting, dependency, CI/security, integration, frontend E2E, SLO, and documentation changes where possible.
2. Prefer production calibration and runbooks over new feature breadth.
3. Raise frontend coverage on high-value shared surfaces first, not by chasing percentage alone.
4. Treat SLO panels as operational contracts: tune them with real traffic evidence before adding more panels.

## Phase 0 — Review And Release Packaging [P0]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-00 | Split PR / commit plan for the current large diff | [x] | Review groups documented in `docs/q11-pr-split-plan.md`: format baseline, dependency compatibility, quality gates, security automation, integration/E2E, SLO/docs |
| Q11-01 | Create release notes from Q10 evidence | [x] | `docs/q10-release-notes.md` links `docs/q10-acceptance-summary.md` and lists risk / rollback notes |
| Q11-02 | Final CI matrix replay | [x] | Local and GitHub runner evidence is recorded in `docs/q11-ci-matrix-evidence.md`; final `main` matrix at `c1ef60c` passed CI, Security, Integration, Release readiness, and E2E |

## Phase 1 — SLO Production Calibration [P1]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-10 | Calibrate API availability and P95 windows | [x] | `docs/slo-guide.md` records the current pre-production evidence window, production adoption windows, target rationale, and deferred alert/release-gate decisions |
| Q11-11 | Add SLO triage runbook | [x] | `docs/slo-guide.md` maps availability, latency, run success, and error-budget breaches to first checks, escalation points, and an incident record template |
| Q11-12 | Decide alerting thresholds | [x] | `docs/slo-guide.md` explicitly defers paging-grade SLO alerts until production Prometheus history exists and records draft thresholds / enablement criteria |

## Phase 2 — Frontend Coverage Growth [P1]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-20 | Add tests for project/module/case navigation utilities | [x] | `frontend/src/utils/caseNavigation.spec.ts` covers route id parsing, review-status parsing, case-list query building, project -> cases links, case detail links, and query-vs-param precedence |
| Q11-21 | Add tests for suite / plan list pure helpers | [x] | `frontend/src/utils/suiteList.spec.ts` and `frontend/src/utils/planList.spec.ts` cover config normalization, status / schedule colors, duration / percent formatting, cron validation / preset parsing, run summaries, failure extraction, and suite run progress helpers |
| Q11-22 | Add one smoke component test for a system page | [x] | `frontend/src/views/system/EnvironmentList.spec.ts` covers project-selection, loading, empty, and API-error states without DOM snapshots; the CaseList E2E mock now matches the array response contract |

## Phase 3 — Operational Runbooks [P1]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-30 | Update release-readiness runbook for Q10 gates | [x] | `docs/q9-release-checklist.md` now covers same-SHA evidence, lint, format, mypy, coverage, security, integration, E2E, SLO JSON, images, migration, Helm, staging smoke, and rollback gates; workflow/static contracts protect the required commands |
| Q11-31 | Add incident drill checklist for failed scheduled plan runs | [x] | `docs/scheduled-plan-incident-drill.md` covers Beat/Celery, Redis DB roles, PostgreSQL state reconciliation, notification and bug-tracker side effects, duplicate-safe recovery, controlled staging drills, and incident evidence |
| Q11-32 | Document rollback for dependency/security updates | [x] | `docs/dependency-security-rollback.md` covers clean backend environments, paired frontend manifest/lockfile rollback, immutable image digests, scanner rollback, vulnerability exceptions, schema compatibility, staging, and audit evidence; frontend image builds now use `npm ci` |

## Phase 4 — Runtime Polish [P2]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-40 | Investigate known Vite ResizeObserver E2E warning | [x] | Root cause was Ant Design Vue measuring an empty CaseList table with horizontal scroll; `scroll.x` is now enabled only when rows exist, the shared e2e fixture now fails any spec on unexpected uncaught page errors (with ResizeObserver noise allowlisted), and full E2E runs without the warning |
| Q11-41 | Review frontend bundle warning | [x] | `docs/frontend-bundle-decision.md` records the Ant/icons split decision and rejected merge experiment; mobile report pages now use modular ECharts imports, reducing the ECharts chunk from 1126.62/374.44 gzip kB to 563.41/191.53 kB with no build warning |
| Q11-42 | Android Docker worker connectivity rehearsal | [x] | `docs/android-worker-connectivity-rehearsal.md` records worker ADB and Docker Desktop host-server evidence, direct/shared topologies, 5037 vs device/Flower 5555, Linux/Desktop/Kubernetes constraints, safe doctor flags, and the remaining physical-device data-plane step |

## Next Action

Q11 roadmap complete. Archive acceptance evidence and continue with the next optimization roadmap.
