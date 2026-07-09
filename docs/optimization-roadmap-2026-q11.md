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
| Q11-10 | Calibrate API availability and P95 windows | [ ] | `docs/slo-guide.md` records observed traffic window and target rationale |
| Q11-11 | Add SLO triage runbook | [ ] | Runbook maps availability, latency, run success, and error-budget breaches to first checks |
| Q11-12 | Decide alerting thresholds | [ ] | Grafana alert template or explicit deferred decision is documented |

## Phase 2 — Frontend Coverage Growth [P1]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-20 | Add tests for project/module/case navigation utilities | [ ] | Vitest covers at least two high-risk route/state helpers |
| Q11-21 | Add tests for suite / plan list pure helpers | [ ] | Run summary, status color, config normalization, or action visibility helpers covered |
| Q11-22 | Add one smoke component test for a system page | [ ] | Shared loading/empty/error behavior covered without brittle DOM snapshots |

## Phase 3 — Operational Runbooks [P1]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-30 | Update release-readiness runbook for Q10 gates | [ ] | Commands include lint, mypy, coverage, security, integration, E2E, SLO JSON validation |
| Q11-31 | Add incident drill checklist for failed scheduled plan runs | [ ] | Checklist covers Celery, Redis, DB row state, notifications, and bug tracker side effects |
| Q11-32 | Document rollback for dependency/security updates | [ ] | Backend and frontend rollback path references lockfiles, requirements, and audit commands |

## Phase 4 — Runtime Polish [P2]

| ID | Task | Status | Acceptance |
|----|------|--------|------------|
| Q11-40 | Investigate known Vite ResizeObserver E2E warning | [ ] | Either suppressed safely in test harness or documented as harmless with evidence |
| Q11-41 | Review frontend bundle warning | [ ] | Known Ant Design circular chunk warning has explicit decision: accepted, split, or tracked |
| Q11-42 | Android Docker worker connectivity rehearsal | [ ] | ADB over TCP path verified or documented with host-network constraints |

## Next Action

Continue Q11-10: calibrate API availability and P95 windows in `docs/slo-guide.md`, recording the observed traffic window and target rationale before adding new panels or alerts.
