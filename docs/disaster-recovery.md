# ATP Disaster Recovery Runbook

This runbook covers PostgreSQL backups created by `scripts/backup-postgres.sh`
and restored by `scripts/restore-postgres.sh`.

## Scope

- PostgreSQL application database.
- Backup objects stored in MinIO under `pg-backups/daily/` and
  `pg-backups/weekly/`.
- Restore from either a local `.sql.gz` file or a MinIO object.

MinIO object storage is not restored by this procedure. Keep MinIO bucket
replication or an external object backup policy for screenshots, reports, APKs,
and scripts.

## Backup

Required environment variables:

```bash
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=atp
POSTGRES_USER=atp
POSTGRES_PASSWORD=...
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=...
MINIO_BUCKET=atp
```

Create a daily backup:

```bash
BACKUP_KIND=daily sh scripts/backup-postgres.sh
```

Create a weekly backup:

```bash
BACKUP_KIND=weekly sh scripts/backup-postgres.sh
```

The generated object path is:

```text
pg-backups/{daily|weekly}/atp-YYYYMMDD-HHMMSS.sql.gz
```

## Restore

Restores are destructive. The restore script refuses to run unless the
`--i-know-this-overwrites` flag is present.

Restore from a MinIO object:

```bash
sh scripts/restore-postgres.sh \
  --i-know-this-overwrites \
  --object pg-backups/daily/atp-20260528-010000.sql.gz
```

Restore from a local dump file:

```bash
sh scripts/restore-postgres.sh \
  --i-know-this-overwrites \
  --file /backups/atp-20260528-010000.sql.gz
```

The script terminates active database sessions, drops the configured database,
recreates it with the configured owner, and loads the gzip-compressed plain SQL
dump with `psql -v ON_ERROR_STOP=1`.

## Kubernetes Drill

1. Scale API and workers down to stop writes:

   ```bash
   kubectl -n atp scale deploy/atp-atp-backend --replicas=0
   kubectl -n atp scale deploy/atp-atp-worker --replicas=0
   kubectl -n atp scale deploy/atp-atp-beat --replicas=0
   ```

2. Run the restore script from an ops image that has `psql`, `gzip`, and `mc`.
   Use the same `POSTGRES_*` and `MINIO_*` values as the ATP release.

3. Run migrations after restore:

   ```bash
   kubectl -n atp exec deploy/atp-atp-backend -- alembic upgrade head
   ```

4. Scale services back:

   ```bash
   kubectl -n atp scale deploy/atp-atp-backend --replicas=2
   kubectl -n atp scale deploy/atp-atp-worker --replicas=3
   kubectl -n atp scale deploy/atp-atp-beat --replicas=1
   ```

5. Verify:

   ```bash
   curl -fsS https://atp.example.com/health
   kubectl -n atp logs deploy/atp-atp-backend --tail=100
   kubectl -n atp logs deploy/atp-atp-worker --tail=100
   ```

## Drill Checklist

- [ ] A recent daily backup exists in MinIO.
- [ ] A recent weekly backup exists in MinIO.
- [ ] Restore script was tested in a non-production namespace.
- [ ] `alembic upgrade head` was run after restore.
- [ ] Backend `/health` returns success after services are restored.
- [ ] A smoke test login and one historical report lookup succeeded.
- [ ] Drill date, backup object, restore duration, and operator were recorded.
