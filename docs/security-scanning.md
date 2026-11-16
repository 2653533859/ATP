# Security Scanning

> Last updated: 2026-08-17

## Bandit SAST

Q10 Phase 4 has started with a backend Bandit gate.

Local command:

```bash
make security-bandit
```

CI command:

```bash
python -m bandit -c pyproject.toml -r backend/app -ll
```

Policy:

- Medium and high severity findings fail the gate.
- Low severity findings are visible but do not block this initial baseline.
- Tests and Alembic migrations are excluded from the scan target.

Initial baseline on 2026-07-06:

- Bandit version: `1.9.4`
- Python 3.14 local scan: passed after fixing the only high-severity finding.
- Remaining low-severity findings are mostly:
  - `try/except/pass` patterns
  - subprocess usage in controlled Android/k6 execution paths
  - hardcoded string false positives such as field names
  - XML parsing warning in export code

The previous `bandit==1.8.0` was not compatible with Python 3.14 because it still referenced `ast.Num`; the baseline uses `1.9.4`.

## Dependency Audit

Q10 Phase 4 dependency scanning baseline is now runnable locally.

Backend command:

```bash
make security-pip-audit
```

Frontend command:

```bash
make security-npm-audit
```

Aggregate command:

```bash
make security-deps
```

Initial baseline on 2026-07-06:

- `pip-audit==2.9.0` against `backend/requirements.txt`: 111 packages checked, 6 vulnerable packages, 25 vulnerability records, 24 with known fix versions.
- Backend packages needing upgrade review: `python-jose`, `python-multipart`, `pytest`, `jinja2`, `cryptography`, `starlette`.
- `npm audit --audit-level=moderate`: 16 vulnerability records (`9` moderate, `5` high, `2` critical).
- Frontend direct packages needing upgrade review include `vitest` / `@vitest/coverage-v8`, `vite`, `axios`, `echarts`, and `vue-i18n`.

Policy status:

- The scan commands intentionally fail when vulnerabilities are present.
- As of 2026-07-08, both dependency audit commands pass with zero known vulnerabilities.
- CI blocking can now be added for high/critical dependency findings.

Remediation completed on 2026-07-08:

- Backend upgrades: `fastapi==0.139.0`, `starlette==1.3.1`, `python-multipart==0.0.32`, `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `jinja2==3.1.6`, `cryptography==48.0.1`, `prometheus-fastapi-instrumentator==8.0.2`.
- Q11 replay update: `python-jose[cryptography]==3.5.0` was replaced with `PyJWT[crypto]==2.13.0` after `pip-audit` reported `ecdsa 0.19.2` / `PYSEC-2026-1325` with no fixed `ecdsa` version available.
- Frontend upgrades: Vite/Vitest 8/4 line, `axios==1.18.1`, `echarts==6.1.0`, `vue-i18n==9.14.5`, `jsdom==29.1.1`, `vue-tsc==3.3.6`.
- npm overrides: `brace-expansion==5.0.7`, `form-data==4.0.6`, `lodash==4.18.1`, `lodash-es==4.18.1`.
- Verification: `make security-pip-audit PYTHON=backend/.venv/bin/python` and `make security-npm-audit` pass.

Remote failure remediation on 2026-08-17:

- Frontend `nanoid` was updated from `3.3.17` to `3.3.18` in `frontend/package-lock.json`; `npm audit --audit-level=high` now reports zero vulnerabilities locally.
- The Worker no longer copies a prebuilt k6 binary whose Go runtime is outside the current security baseline. It builds k6 `v2.2.0` from a verified commit with a pinned Go `1.26.6` builder image digest.
- The Worker Docker build now replaces fixed-version JMeter dependencies (Jackson, XStream, dnsjava, json-smart, HttpCore5 and Batik) and removes the current executor's unused Neo4j/Tika optional jars; this keeps the JMeter CLI/report path while removing the vulnerable bundled versions.
- Three application XML parsers now use `defusedxml`; the standalone test sweep also bootstraps all SQLAlchemy models in `test_mobile_special_events.py` so it no longer depends on another test file's import order.
- The first remote rerun passed npm audit but exposed the Bandit, standalone-test and Worker Trivy issues above. The second rerun passed CI and Security's non-Trivy jobs; the following k6 source-build rerun failed only because the entry path was written as `./cmd/k6` instead of the v2.2.0 `./cmd` package, which is now corrected.

Worker Trivy remediation on 2026-11-16 (Security run 43696416034 reported 10 HIGH in `usr/local/bin/k6` and 6 HIGH + 1 CRITICAL in JMeter jars):

- k6 is now built from `v2.4.0` (commit `dd9395906d48437a8d7ab53e309afa47ad8d67e0`) with the pinned Go `1.26.11` builder image digest. Its `go.mod` carries `golang.org/x/crypto v0.58.0`, `golang.org/x/net v0.62.0`, `golang.org/x/text v0.43.0` and `google.golang.org/grpc v1.84.0`, all at or above the fixed versions Trivy listed; Go `1.26.11` is above the stdlib fixes (`1.26.9` / `1.26.10`). `v2.3.0` was not enough (`x/net v0.58.0` is below the `0.60.0` / `0.62.0` fixes).
- JMeter stays at 5.6.3 as an optional executor; the manual jar replacement now uses Jackson `2.18.11` and additionally swaps `freemarker-2.3.32` for `2.3.35` and `jsoup-1.17.1` for `1.23.2`.
- These changes were made without a local Docker daemon, Go toolchain or Trivy: the image build, the `k6 version` / `jmeter --version` smoke lines in the Dockerfile and the Trivy result must be confirmed by the next `Security` and `Release readiness` workflow runs.
- The `Trivy image scan` job is now a `fail-fast: false` matrix, so a failing worker scan no longer hides the frontend scan.

## Next Scans

## Security Workflow

Q10 Phase 4 security automation is now represented by `.github/workflows/security.yml`.

Jobs:

- Gitleaks secret scanning.
- Backend `pip-audit`.
- Frontend `npm audit --audit-level=high`.
- Trivy image scans for backend, worker, and frontend images with HIGH/CRITICAL gating.

Dependabot is configured in `.github/dependabot.yml` for:

- pip dependencies under `/backend`
- npm dependencies under `/frontend`
- Dockerfiles under `/backend` and `/frontend`
- GitHub Actions under `/`

## Next Scans

- Decide whether to add a local Gitleaks pre-commit hook after confirming the preferred developer installation path.
- Add security workflow artifacts or SARIF upload if review workflows need richer vulnerability triage.

Dependency, lockfile, image, scanner, and vulnerability rollback decisions follow `docs/dependency-security-rollback.md`.
