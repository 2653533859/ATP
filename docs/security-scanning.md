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
- The Worker k6 base image was updated from `grafana/k6:2.1.0` to the versioned `grafana/k6:2.2.0` image to pick up upstream Go dependency fixes; the remote Trivy result must still be confirmed after the next push.

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
