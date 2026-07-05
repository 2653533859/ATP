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
