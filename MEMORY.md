# MEMORY

## Recent Fixes (2026-07-08)

- Fixed the manual bug-link API so `POST /runs/{run_id}/link-bug` now verifies the caller has `editor` access to the run's project before mutating `run.result_summary`.
- Added the previously untracked AI governance and failure diagnosis service modules to the working diff so clean checkouts include imports used by run failure diagnosis and AI case generation.
- Fixed a bug-status audit log regression that referenced an undefined `body.bug_id`; it now records the existing linked bug id from `bug_info`.
- Added static regression coverage for manual bug linking permissions.
- Fixed Python 3.14 local backend setup by installing Homebrew `libpq`, exporting the keg-only `libpq` / `openssl@3` build flags, and adding Python-version-specific dependency pins for SQLAlchemy, grpcio/grpcio-tools, Playwright, and OpenTelemetry.
- Validation: `backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration` passed (`823 passed`); targeted bug/diagnosis tests passed (`10 passed`); `py_compile` and `git diff --check` passed.
- Validation update: Docker `python:3.12-slim-bookworm` target-runtime backend regression passed (`823 passed`), confirming the Python 3.14 conditional pins do not break the Python 3.12 deployment baseline.
- Frontend quality update: `npm run type-check` and `npm run build` passed; build only reports the known `ant-design-icons -> ant-design -> ant-design-icons` circular chunk warning.
- Release closeout update: added `docs/release-evidence-2026-07-06.md` with PR grouping, test evidence, known warning, and risk notes; targeted compatibility regression passed (`18 passed`).
- Q10 Phase 1 started: added `ruff==0.8.4` dev tooling, root `pyproject.toml` ruff config, `make lint`, a CI `backend-lint` job, and `docs/code-quality.md`. The first gate checks F821/F822/F823 and passes locally.
- Q10 coverage gate started: added pytest-cov tooling, coverage config, `make test-backend-coverage`, CI coverage XML artifact upload, and a 52% `--cov-fail-under` gate based on the current 53.47% local baseline.
- Frontend unit testing started: added Vitest/jsdom/test-utils/coverage-v8, `npm run test`, `npm run test:coverage`, CI frontend unit-test step, and first specs for auth store, HTTP interceptors, permissions utilities, WebSocket reconnect/message handling, and `BatchOperationBar`.
- Pre-commit baseline added: `.pre-commit-config.yaml` now runs YAML/EOF/trailing whitespace hooks, backend ruff, and frontend Vitest. Helm templates are excluded from plain YAML parsing; initial EOF hook fixes were applied to existing files.
- Mypy baseline added for `backend/app/core`, `backend/app/schemas`, and `backend/app/services` (`76` files). Fixed low-risk Optional handling and variable-reuse type issues, added `types-PyYAML`, and wired mypy into CI/pre-commit.
- Bandit SAST baseline added with `bandit==1.9.4`, `make security-bandit`, pyproject config, CI execution, and `docs/security-scanning.md`. The only high finding was fixed by marking report-cache MD5 as `usedforsecurity=False`; medium/high gate now passes with 63 low findings visible.
- Dependency audit baseline added with `pip-audit==2.9.0`, `make security-pip-audit`, `make security-npm-audit`, and `make security-deps`. The initial baseline had backend 6 vulnerable packages / 25 records and frontend 16 npm audit records (`9` moderate, `5` high, `2` critical).
- Dependency audit remediation completed on 2026-07-08: upgraded FastAPI/Starlette, python-multipart, pytest/pytest-asyncio, Jinja2, cryptography, prometheus-fastapi-instrumentator, Vite/Vitest, Axios, ECharts, vue-i18n, jsdom, vue-tsc, and npm overrides for `brace-expansion`, `form-data`, `lodash`, and `lodash-es`. Q11-02 replay then replaced `python-jose` with `PyJWT[crypto]==2.13.0` to remove the vulnerable transitive `ecdsa` chain. `make security-pip-audit` and `make security-npm-audit` now both pass with zero known vulnerabilities.
- Ruff format baseline completed on 2026-07-08: ran `ruff format backend/app backend/tests` (`217` files reformatted, `115` unchanged), added `make format` / `make format-check`, wired `ruff format --check` into CI and pre-commit, and added `.git-blame-ignore-revs` instructions for the future format-only commit SHA.
- Security automation added on 2026-07-08: `.github/workflows/security.yml` now runs Gitleaks, backend `pip-audit`, frontend high/critical `npm audit`, and Trivy image scans for backend/worker/frontend. `.github/dependabot.yml` now covers pip, npm, Docker, and GitHub Actions weekly.
- Frontend unit testing expanded on 2026-07-08 with `stores/theme` and `utils/chartTheme` specs. Vitest now has 7 files / 18 tests and full-source coverage visibility is 1.8%.
- Docker Python 3.12 target-runtime regression was rerun after dependency remediation. The first attempt exposed `pytest-playwright==0.5.2` requiring `pytest<9`; `pytest-playwright` / `playwright` pins were unified to the 0.8.0 / 1.61.0 line, and the Docker Python 3.12 backend suite then passed (`823 passed`).
- Q10 Phase 5 integration expansion started: added `backend/tests/integration/test_suite_plan_flow.py` for project/module/API case approval -> suite run -> plan run. The first real-infra run exposed a missing Alembic column for `test_suites.config`; added migration `20260529_0039_add_suite_config.py` plus migration regression coverage. Fresh Postgres/Redis/MinIO integration environment now passes (`8 passed`).
- Q10 Phase 5 integration expansion continued: added `backend/tests/integration/test_notification_bug_flow.py` for notification masking/test-send failure handling and bug tracker connection/dedup/create/status/manual-link flows. The real-infra run exposed `bug_trackers.tracker_type` still being varchar in Alembic-created databases; added `20260529_0040_convert_bug_tracker_type_enum.py` plus migration regression coverage. Integration tests now pass on fresh real infra and repeat runs (`10 passed`).
- Q10 Phase 5 frontend E2E expansion continued: added suite / plan mock fixtures and `frontend/e2e/suite-plan.spec.ts`, covering suite load -> trigger run -> history drawer and plan load -> manual run -> execution history. Also added a shared `/api/v1/runs` mock to remove dashboard proxy noise after login. Targeted suite-plan E2E passed (`2 passed`), full Playwright E2E passed (`9 passed`), `npm --prefix frontend run type-check` passed, and Vitest remained green (`18 passed`).
- Q10 Phase 5 SLO thin slice completed: added `atp_run_outcomes_total{entity_type,status}` for terminal case/suite/plan outcomes, recorded outcomes in standalone case, parameterized case, suite, and plan worker paths, expanded `ATP Overview` with API availability, API P95, run success rate, and API error-budget panels, and added `docs/slo-guide.md` plus observability-guide updates.
- Q10 Phase 5 flaky governance completed: added `pytest-rerunfailures==16.4`, registered a `flaky` pytest marker, enabled one bounded retry for scheduled/manual backend integration CI, documented Playwright CI retry boundaries, and added `docs/flaky-governance.md`.
- Q10 acceptance closure completed: added `docs/q10-acceptance-summary.md`, updated README with a Q10 quality/stability index, and synced Task / MEMORY / CONTEXT / release evidence.
- Q11 optimization roadmap started: added `docs/optimization-roadmap-2026-q11.md` with Phase 0 release packaging, Phase 1 SLO calibration, Phase 2 frontend coverage growth, Phase 3 runbooks, and Phase 4 runtime polish.
- Q11-00 completed: added `docs/q11-pr-split-plan.md` with nine recommended review units covering dependency compatibility, runtime fixes, quality gates, Ruff format baseline, security automation, integration, frontend E2E, SLO/flaky governance, and documentation closure. Next action is Q11-01 release notes with risk / rollback notes.
- Q11-01 completed: added `docs/q10-release-notes.md` with Q10 release summary, major change groups, verification snapshot, risk notes, rollback plan, and release checklist. Next action is Q11-02 final CI matrix evidence collection.
- Q11-02 completed on 2026-07-09: `docs/q11-ci-matrix-evidence.md` now archives local and GitHub runner evidence. The final `main` matrix at `c1ef60c` passed CI (`28998360621`), Security (`28998360606`), Integration (`28998366738`), Release readiness (`28998368776`), and E2E (`28998370798`). Follow-up fixes included `types-redis`, a typed Redis async-close helper, Trivy action `v0.36.0`, scoped Gitleaks allowlists, observability wording alignment, worker k6 refresh to `grafana/k6:2.1.0`, and frontend runtime `apk upgrade --no-cache`.
- Q11-10 completed on 2026-07-09: `docs/slo-guide.md` now records the current pre-production evidence window, the missing production Prometheus-history caveat, 7-day initial and 14-day stable production calibration windows, target rationale for API availability / P95 / run success rate, and deferred decisions for paging alerts, monthly error budgets, release-blocking SLO policy, and endpoint-class SLOs.
- Q11-11 completed on 2026-07-09: `docs/slo-guide.md` now includes a SLO triage runbook with first-five-minute checks, availability / latency / run-success / error-budget playbooks, escalation points, and an incident record template.
- Q11-12 completed on 2026-07-09: `docs/slo-guide.md` now explicitly defers paging-grade SLO alerts until production Prometheus history exists, keeps the existing platform health alerts as the active alert layer, and records draft thresholds / enablement criteria for future availability, P95, error-budget, and run-success alerts.
- Next Q11 action: start Q11-20 frontend coverage growth by adding tests for high-risk project/module/case navigation utilities.

## Recent Fixes (2026-06-03)

- Unified several system settings pages onto the shared `page-shell` / `page-hero` visual pattern and added missing zh-CN/en-US subtitle copy for environment, notification, global variable, and bug tracker pages.
- Hardened FastAPI startup against transient or misconfigured MinIO by using short MinIO client timeouts and logging bucket bootstrap failures as warnings instead of blocking app startup.
- Added `scripts/dev_mock_backend.py` as a lightweight local UI-preview backend for cases where external PostgreSQL / Redis / MinIO dependencies are unavailable.
- Verified the real FastAPI service can start successfully on `http://127.0.0.1:8000` after the MinIO startup hardening; `/health` returned `{"status":"ok"}`.

## Recent Fixes (2026-03-08)

- Completed Phase 4.5 notification integration across backend, frontend, migration, and docs.
- Added notification config model/schema/API/service, notification settings UI, and SMTP-related environment documentation.
- Added regression tests for notification dispatch, notification API test-send behavior, startup model loading, and migration coverage.
- Fixed notification read-path credential exposure by requiring engineer-level access for notification detail/list endpoints.
- Fixed WeCom and DingTalk delivery handling so non-200 responses or non-zero `errcode` values now raise errors instead of being reported as success.
- Fixed project deletion regression by cascading `notification_configs` on project delete at both ORM and migration/foreign-key levels.
- Restored frontend type-check by installing missing `vuedraggable` / `sortablejs` dependencies.
- Updated `Task.md` to mark 4.5 notification integration complete and recorded the security/correctness hardening items.

## Previous Fixes (2026-03-06)

- Fixed device mirror auth flow by loading screenshots through Axios with token and rendering `Blob` URLs in frontend polling.
- Added `android-tools-adb` to backend runtime image so mirror screenshot endpoints can run in container deployments.
- Fixed Android low-code `clear=true` input behavior by sending repeated valid delete key events (`keyevent 67`).
- Switched APK upload path to chunked tempfile streaming to avoid loading large APK files fully into memory.
- Added regression tests for Android low-code clear behavior and APK streaming size guard.

## Validation Snapshot

- `backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration` passed on local Python 3.14 (`825 passed`).
- Docker `python:3.12-slim-bookworm` with `gcc libpq-dev` installed ran `python -m pytest backend/tests -q --ignore=backend/tests/integration` successfully (`823 passed`).
- `npm --prefix frontend run type-check` and `npm --prefix frontend run build` passed; build has only the known Ant Design icons circular chunk warning.
- `backend/.venv/bin/python -m pytest backend/tests/services/test_device_sync.py backend/tests/api/test_ai_llm_configs_api.py backend/tests/worker/test_async_runner.py backend/tests/worker/test_suite_execution_config.py -q` passed (`18 passed`).
- `make lint PYTHON=backend/.venv/bin/python` passed (`ruff check backend/app backend/tests`).
- `make mypy PYTHON=backend/.venv/bin/python` passed (`Success: no issues found in 76 source files`).
- `make security-bandit PYTHON=backend/.venv/bin/python` passed (`Medium: 0`, `High: 0`, `Low: 63`).
- `make security-pip-audit PYTHON=backend/.venv/bin/python` passed (`No known vulnerabilities found`).
- `make security-npm-audit` passed (`found 0 vulnerabilities`).
- `make format-check PYTHON=backend/.venv/bin/python` passed (`336 files already formatted`).
- YAML parse validation passed for `.github/workflows/security.yml`, `.github/dependabot.yml`, `.github/workflows/ci.yml`, and `.pre-commit-config.yaml`.
- `make pre-commit PYTHON=backend/.venv/bin/python` passed all hooks.
- Q11-02 GitHub runner final matrix passed on `main` commit `c1ef60c`: CI, Security, Integration, Release readiness, and E2E were all successful. Details and run links are archived in `docs/q11-ci-matrix-evidence.md`.
- Q11-10 SLO calibration is documented in `docs/slo-guide.md`; current targets remain pre-production guardrails until continuous production Prometheus history is available.
- Q11-11 SLO triage runbook is documented in `docs/slo-guide.md`; it maps each current SLO breach to first checks and escalation criteria.
- Q11-12 alert threshold decision is documented in `docs/slo-guide.md`; SLO-specific paging alerts are deferred until production Prometheus history exists.
- `make test-backend-coverage PYTHON=backend/.venv/bin/python` passed (`823 passed`, total coverage `53.47%`, required `52%` reached).
- Docker `python:3.12-slim-bookworm` with `gcc libpq-dev` installed ran `python -m pytest backend/tests -q --ignore=backend/tests/integration` successfully after dependency remediation (`823 passed`).
- `npm --prefix frontend run test` passed (`18 passed`); `npm --prefix frontend run test:coverage` passed with current frontend full-source coverage baseline `1.8%`; `npm --prefix frontend run type-check` and `npm --prefix frontend run build` passed.
- `npm --prefix frontend run e2e -- suite-plan.spec.ts` passed (`2 passed`), and full `npm --prefix frontend run e2e` passed (`9 passed`) after adding suite / plan workflow coverage.
- SLO thin-slice validation passed: `python3 -m json.tool docker/grafana/dashboards/atp-overview.json`, `backend/.venv/bin/python -m ruff check backend/app/core/metrics.py backend/app/worker/tasks.py backend/tests/worker/test_run_outcome_metrics.py`, and `backend/.venv/bin/python -m pytest backend/tests/worker/test_run_outcome_metrics.py backend/tests/worker/test_dataset_parameterized.py backend/tests/worker/test_plan_execution_config.py backend/tests/worker/test_suite_execution_config.py -q` (`23 passed`).
- Flaky governance validation passed: installed `backend/requirements-dev.txt`, `pytest --markers` shows both project `flaky` marker and rerunfailures marker, `pytest backend/tests/worker/test_run_outcome_metrics.py -q --reruns 1 --reruns-delay 1` passed (`2 passed`), and CI workflow YAML parsing passed.
- Q10 acceptance closure is documented in `docs/q10-acceptance-summary.md`; README now links Q10 implementation and acceptance artifacts.
- Fresh real-infra integration run passed with temporary local services on Postgres `55432`, Redis `6380`, and MinIO `19000`: `alembic upgrade head` succeeded and `backend/tests/integration -m integration` passed (`10 passed`); a second run against the same database also passed (`10 passed`).
- `pytest backend/tests/api/test_notifications.py backend/tests/services/test_notifier.py backend/tests/migrations/test_notification_config_migration.py backend/tests/services/test_notification_bootstrap.py backend/tests/plans/test_plan_regressions.py backend/tests/api/test_webhook_exports_regressions.py -q` passed (`20 passed`).
- `npm --prefix frontend run type-check` passed after restoring missing frontend dependencies.

## Related Commits

- `a970cd2`: notification integration, security fixes, Task update, and supporting docs/tests.
- `b7f7698`: mirror/auth + clear/upload regressions.
- `c6df8fc`: latest feature repairs and task doc updates.
