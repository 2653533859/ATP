# ATP Backup and Restore Drill Record

Use this document to record every non-production or production backup/restore
drill. Keep one section per drill and attach command output, screenshots, or
ticket links when available.

## Drill Record Template

| Field | Value |
|-------|-------|
| Drill date | YYYY-MM-DD |
| Environment | non-production / production |
| Operator | name |
| PostgreSQL backup object | `pg-backups/daily/atp-YYYYMMDD-HHMMSS.sql.gz` |
| PostgreSQL backup size | bytes or MiB |
| MinIO object backup location | `dr-minio/<bucket>/atp-objects/` or `/backups/minio/atp-objects/` |
| MinIO object backup size | bytes or MiB |
| Restore start time | HH:MM UTC |
| Restore end time | HH:MM UTC |
| Restore duration | minutes |
| Migration result | `alembic upgrade head` output summary |
| Health check result | `/health` status |
| Smoke test result | login, historical report lookup, restored object fetch |
| Restored object key checked | object key |
| Rollback needed | yes / no |
| Notes | links to logs, screenshots, incident/release ticket |

## Required Evidence

- `mc ls` output showing the selected PostgreSQL backup object.
- `mc du` output for the MinIO application object backup target.
- Restore command output from `scripts/restore-postgres.sh`.
- Object restore command output from `mc mirror --overwrite --remove`.
- `alembic upgrade head` result after database restore.
- Backend `/health` response after services are scaled back.
- Smoke test evidence for login, one historical report lookup, and one restored
  object fetch or signed URL access.

## 2026-07-05 Repository Verification

| Field | Value |
|-------|-------|
| Drill date | 2026-07-05 |
| Environment | repository static verification |
| Operator | Codex |
| PostgreSQL backup object | documented as `pg-backups/{daily\|weekly}/atp-YYYYMMDD-HHMMSS.sql.gz` |
| PostgreSQL backup size | not applicable without live MinIO |
| MinIO object backup location | documented as `dr-minio/${DR_MINIO_BUCKET}/atp-objects/` |
| MinIO object backup size | not applicable without live MinIO |
| Restore duration | not applicable without live environment |
| Migration result | documented Kubernetes drill step requires `alembic upgrade head` |
| Health check result | documented Kubernetes drill step requires `/health` check |
| Smoke test result | documented checklist requires login, report lookup, and restored object fetch |
| Restored object key checked | to be filled during live drill |
| Rollback needed | no repository changes require rollback |
| Notes | Static tests verify database script references, MinIO backup/restore commands, drill checklist, and this record template. |

## 2026-09-10 Single-node C1.3 Drill

| Field | Value |
|-------|-------|
| Drill date | 2026-09-10 |
| Environment | `atp-single-node` integration; host-local external data services |
| Operator | Codex |
| PostgreSQL backup object | `pg-backups/daily/atp-20260910-103140.sql.gz` |
| PostgreSQL backup size | 65,254 bytes |
| PostgreSQL restore target | isolated temporary database, removed after verification |
| PostgreSQL restore check | 65 public tables, 4 projects, 4 users and `20260909_0072` matched source |
| Redis backup | 34,165,810-byte RDB snapshot; SHA-256 recorded in linked evidence |
| Redis restore check | isolated Redis container returned the exact probe; source probe and temporary snapshot/container removed |
| MinIO object restore | same-endpoint probe source/restore SHA-256 matched; temporary prefix empty |
| Migration result | restored database contained `20260909_0072`; live Backend remained at head |
| Health check result | Helm revision 41 deployed, Backend `/health` returned `ok`, 6/6 Pods Ready and zero restarts |
| Smoke test result | real maintenance queue backup completed; default/maintenance/performance/node queues returned to zero |
| Rollback needed | no |
| Notes | [`evidence/c1-data-services-recovery-2026-09-10.json`](evidence/c1-data-services-recovery-2026-09-10.json). C1.3 validation is complete, but over-privileged PostgreSQL/Redis/MinIO credentials, RDB-only Redis recovery and same-host MinIO keep C3/P4 blocked. |

## 2026-09-12 Single-node C3.3 Migration and Restore Drill

| Field | Value |
|-------|-------|
| Drill date | 2026-09-12 |
| Environment | `atp-single-node` integration; isolated temporary databases on the host-local PostgreSQL service |
| Operator | Codex |
| PostgreSQL backup object | `pg-backups/daily/atp-20260911-181920.sql.gz` |
| PostgreSQL backup size | 65,259 bytes |
| Empty migration | base → `20260909_0072`; 65 public tables, including `alembic_version` |
| Upgrade/rollback cycle | `20260909_0071 → 20260909_0072 → 20260909_0071 → 20260909_0072` |
| Restore check | 65 public tables, 4 projects, 4 users and migration head `20260909_0072` |
| Runtime privilege check | project read, table DML and sequence usage passed; schema `CREATE` denied |
| Health check result | Helm revision 44 deployed; 6/6 Pods Ready, zero restarts and 40-second bounded sampling produced zero alerts |
| Rollback needed | no; the schema downgrade was confined to an isolated database |
| Cleanup | all temporary databases, directories and scripts removed |
| Notes | The first restore reproduced missing runtime grants because `--no-acl` excludes ACLs. Commit `6755ed9f` reconciles grants after Alembic and the same backup then passed. Evidence: [`evidence/c3-migration-restore-2026-09-12.json`](evidence/c3-migration-restore-2026-09-12.json). This is still same-host backup evidence, not independent MinIO DR. |
