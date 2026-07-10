# Dependency And Security Update Rollback

> Updated: 2026-07-10
> Scope: backend/frontend dependency pins, lockfiles, base images, security workflows, and vulnerability remediations.

## Principles

- Roll back to a known-good commit or immutable image digest, not to an invented version combination.
- Keep dependency manifests and their generated lockfiles together.
- Validate rollback candidates in clean environments; in-place installs can leave removed transitive packages behind.
- A runtime regression can justify rollback, but reintroducing a known exploitable vulnerability requires an explicit security decision and compensating control.
- Dependency rollback does not imply database downgrade. Verify schema compatibility separately.
- Preserve the failed update and its scan/test evidence for diagnosis; do not force-push or erase the audit trail.

## Scope Inventory

Treat these files as rollback units:

| Area | Files | Unit rule |
| --- | --- | --- |
| Backend runtime | `backend/requirements.txt`, relevant backend code and Dockerfiles | Exact pins and Python markers must match the selected commit |
| Backend quality/security tools | `backend/requirements-dev.txt`, `pyproject.toml`, `.pre-commit-config.yaml` | Revert tool pin and configuration together |
| Frontend runtime/build | `frontend/package.json`, `frontend/package-lock.json`, `frontend/Dockerfile` | `package.json` and lockfile always move together; install with `npm ci` |
| Container base/system packages | `backend/Dockerfile`, `backend/Dockerfile.worker`, `frontend/Dockerfile` | Prefer previously scanned image digest over rebuilding an old floating tag |
| Security automation | `.github/workflows/security.yml`, `.github/dependabot.yml`, scoped scanner config | Automation rollback is independent from vulnerability-fix rollback |

## Decision Gate

Before rollback, record:

- Bad release SHA, known-good SHA, deployment environment, and affected image digests.
- Regression symptom, first bad version, affected workflow/runtime path, and severity.
- Vulnerabilities that the update fixed, including CVE/advisory, exploitability, and exposure.
- Whether a forward fix can be produced inside the incident window.
- Security owner, runtime owner, rollback owner, and go/no-go approver.

Choose one outcome:

1. Forward fix: preferred when the vulnerable old version cannot be safely exposed.
2. Full rollback: restore the complete known-good dependency/source/image set.
3. Partial rollback: only when dependency boundaries and lockfile resolution prove independence.
4. Hold deployment: keep traffic on the prior immutable image while a candidate is rebuilt and scanned.

Do not disable scanners merely to make a rollback candidate green.

## Prepare An Isolated Rollback Candidate

Create a separate worktree from the known-good ref:

```bash
export BAD_REF=<BAD_SHA>
export GOOD_REF=<KNOWN_GOOD_SHA>
git diff --stat "$GOOD_REF" "$BAD_REF" -- \
  backend/requirements.txt backend/requirements-dev.txt \
  frontend/package.json frontend/package-lock.json \
  backend/Dockerfile backend/Dockerfile.worker frontend/Dockerfile \
  .github/workflows/security.yml .github/dependabot.yml
git worktree add ../ATP-rollback "$GOOD_REF"
cd ../ATP-rollback
```

Acceptance:

- `GOOD_REF` is a previously deployed/tested commit, not just the parent of the bad change.
- The rollback diff includes all direct pins, overrides, lockfile changes, base-image changes, and compatibility code.
- No generated dependency directory (`node_modules`, virtualenv, build output) is copied from the bad workspace.

## Backend Rollback

Backend runtime dependencies are exactly pinned in `backend/requirements.txt`, with Python-version markers where required. Validate from a clean environment:

```bash
python3.12 -m venv /tmp/atp-backend-rollback
/tmp/atp-backend-rollback/bin/python -m pip install --upgrade pip
/tmp/atp-backend-rollback/bin/python -m pip install \
  -r backend/requirements.txt -r backend/requirements-dev.txt
/tmp/atp-backend-rollback/bin/python -m pip check
make lint PYTHON=/tmp/atp-backend-rollback/bin/python
make format-check PYTHON=/tmp/atp-backend-rollback/bin/python
make mypy PYTHON=/tmp/atp-backend-rollback/bin/python
make test-backend-coverage PYTHON=/tmp/atp-backend-rollback/bin/python
make security-bandit PYTHON=/tmp/atp-backend-rollback/bin/python
make security-pip-audit PYTHON=/tmp/atp-backend-rollback/bin/python
```

When the reverted change touched Python 3.14 compatibility markers, repeat dependency resolution and the targeted compatibility suite with Python 3.14. Python 3.12 remains the deployment baseline until the runtime matrix changes explicitly.

Check for removed packages that should no longer exist:

```bash
/tmp/atp-backend-rollback/bin/python -m pip freeze
```

Do not validate rollback by installing old requirements over the bad virtualenv. That can leave packages such as removed JWT/transitive dependencies importable even though the manifest no longer declares them.

## Frontend Rollback

Restore `frontend/package.json` and `frontend/package-lock.json` from the same known-good commit. Never run `npm install <package>@<version>` as the rollback mechanism because it mutates resolution state.

```bash
npm --prefix frontend ci
npm --prefix frontend ls --all
npm --prefix frontend run test
npm --prefix frontend run type-check
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=high
```

Acceptance:

- `npm ci` completes without changing `frontend/package-lock.json`.
- Unit tests, type-check, and production build pass.
- High/critical audit is clear or a time-bounded security exception is approved.
- `frontend/Dockerfile` uses `npm ci`, so image resolution matches the committed lockfile.

## Image And Base-Image Rollback

Prefer redeploying the exact previously scanned image digest:

```bash
docker pull registry.local/atp/backend@sha256:<digest>
docker pull registry.local/atp/worker@sha256:<digest>
docker pull registry.local/atp/frontend@sha256:<digest>
```

If a rebuild is mandatory, build from the isolated `GOOD_REF` worktree and assign new rollback-candidate tags:

```bash
docker build -t registry.local/atp/backend:rollback-<GOOD_REF> backend/
docker build -t registry.local/atp/worker:rollback-<GOOD_REF> -f backend/Dockerfile.worker backend/
docker run --rm --entrypoint k6 registry.local/atp/worker:rollback-<GOOD_REF> version
docker build -t registry.local/atp/frontend:rollback-<GOOD_REF> frontend/
```

Scan the exact candidate contents before promotion:

```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 registry.local/atp/backend:rollback-<GOOD_REF>
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 registry.local/atp/worker:rollback-<GOOD_REF>
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 registry.local/atp/frontend:rollback-<GOOD_REF>
```

Do not assume an old tag has old contents, and do not rebuild between staging and production. Record promoted digests.

## Security Automation Rollback

If the scanner workflow itself is broken:

- Revert `.github/workflows/security.yml` and action pins only to the last working workflow.
- Keep dependency and base-image vulnerability fixes unless they caused the confirmed runtime regression.
- Keep Gitleaks history and scoped allowlists; never replace a failing scan with a repository-wide ignore.
- Re-run Gitleaks, pip-audit, npm audit, and all three Trivy scans on the rollback commit.
- Restore branch-protection requirements immediately after an emergency workflow bypass.

If a secret is detected, rollback is not remediation. Rotate/revoke the credential, remove it from active configuration, assess history exposure, and document the incident before restoring the scan.

## Database And Compatibility Check

Dependency/security updates should normally be schema-neutral. If the same release also contains migrations:

- Compare the rollback application's ORM expectations with the current Alembic head.
- Run the rollback image against a restored production-like database before production rollback.
- Keep applied migration files in history and prefer a forward-compatible application rollback.
- Do not run `alembic downgrade` in production without the backup/restore procedure in `docs/migrations.md` and `docs/disaster-recovery.md`.

Run real-infrastructure integration after migration compatibility is established:

```bash
make infra-up
PATH="$PWD/backend/.venv/bin:$PATH" make migrate
make test-integration PYTHON=/tmp/atp-backend-rollback/bin/python
make infra-down
npm --prefix frontend run e2e
```

## Staging And Production Rollback

1. Deploy the rollback candidate digest to staging.
2. Run the smoke paths in `docs/q9-release-checklist.md` and observe SLO/error panels.
3. Confirm the original regression is gone and no fixed vulnerability has become an unapproved blocker.
4. Record current production Helm revision and configuration revision.
5. Promote the already-tested digest or use the previous immutable deployment revision.

```bash
helm history atp -n atp-production
helm rollback atp <REVISION> -n atp-production
```

After production rollback, verify login, case execution, suite/plan runs, worker queues, notifications, bug tracker integration, and API availability/P95/run-success panels.

## Reintroduced Vulnerability Policy

If rollback reintroduces a known vulnerability:

- Block rollback when the vulnerability is remotely exploitable on the deployed path and no compensating control exists.
- Prefer traffic isolation, feature disablement, WAF/network restriction, or a forward patch over exposed rollback.
- Require a written, time-bounded exception with advisory ID, affected component, exposure, mitigation, owner, expiry, and upgrade plan.
- Keep `pip-audit`, `npm audit`, and Trivy output attached to the decision; do not suppress the finding globally.
- Re-open the dependency update immediately after service restoration.

## Evidence And Exit Criteria

Archive:

- `BAD_REF`, `GOOD_REF`, rollback commit, changed manifests, and lockfile diff.
- Clean-environment `pip check`, `pip-audit`, `npm ci`, `npm audit`, tests, and builds.
- Backend/worker/frontend image tags and immutable digests.
- Trivy and Gitleaks workflow URLs/results.
- Migration compatibility and real-infrastructure integration results.
- Staging smoke result, production Helm revision, and SLO observation window.
- Reintroduced vulnerabilities, approved exception, compensating controls, owner, and expiry.

Rollback is complete only when the runtime regression is resolved, the deployed digest is known, required scans are green or explicitly approved, data/schema compatibility is proven, and a forward-fix owner is assigned.
