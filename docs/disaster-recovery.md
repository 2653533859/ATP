# ATP Disaster Recovery Runbook

This runbook covers PostgreSQL backups created by `scripts/backup-postgres.sh`,
database restores through `scripts/restore-postgres.sh`, and MinIO object
storage backup/restore drills.

Celery Worker 的自动备份路径直接调用容器内的 `pg_dump` 和 Python MinIO SDK，
不要求镜像额外安装 `mc`，也不依赖只在仓库根目录存在的运维脚本；根目录脚本仍可供
具备 `pg_dump`/`mc` 的运维主机手工执行。

Worker 镜像显式安装 PostgreSQL 16 客户端，避免 Debian bookworm 的通用
`postgresql-client` 落到 15.x 后拒绝备份 PostgreSQL 16 服务端。2026-08-17 的隔离
备份/恢复演练证据见 [`performance-linux-q18-acceptance-2026-08-17.json`](evidence/performance-linux-q18-acceptance-2026-08-17.json)。

## Scope

- PostgreSQL application database.
- Backup objects stored in MinIO under `pg-backups/daily/` and
  `pg-backups/weekly/`.
- Restore from either a local `.sql.gz` file or a MinIO object.
- MinIO application objects such as screenshots, reports, APKs, uploaded
  scripts, and generated artifacts.

PostgreSQL dump objects live in the same bucket as application objects by
default. Object storage backup commands must exclude `pg-backups/*` when the
target is intended to hold only application objects; database backups remain
validated through the PostgreSQL restore flow below.

## Lifecycle policy boundary

Bucket lifecycle is separate from ATP's database-aware `StoragePolicy` cleanup.
Do not add an expiration rule for the bucket root or for `screenshots/`,
`reports/`, `apks/`, `scripts/`, or `pg-backups/` unless the corresponding
database retention and backup policy has been reviewed. An object lifecycle
rule cannot see whether an object is still referenced by a run or dataset.

The optional Helm hook / Compose profile runs `python -m app.ops_minio_lifecycle`.
It always reconciles an `atp-managed-` rule namespace, preserves rules owned by
other systems, and aborts incomplete multipart uploads. It is disabled by
default; use a scoped prefix such as `tmp/` for any explicit expiration rule.
Inspect the target before and after a change with:

```bash
mc ilm export atp-minio/${MINIO_BUCKET}
mc ilm rule ls atp-minio/${MINIO_BUCKET}
```

Record the resulting rule set and operator approval with the backup/restore
drill evidence. A successful object restore does not by itself prove that the
production lifecycle policy is safe.

The latest read-only audit of the configured target is recorded in
`docs/evidence/minio-lifecycle-audit-2026-08-15.json`. It found no lifecycle
rules and confirmed that the bucket contains objects covered by database
retention/reference policies, so no expiration policy was enabled automatically.

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

## Object Storage Backup

Use MinIO `mc mirror` to copy application objects to a second MinIO/S3
compatible bucket or to a mounted backup volume. The examples intentionally
exclude PostgreSQL dump objects to avoid mixing database backup retention with
application artifact retention.

Mirror to a remote bucket:

```bash
mc alias set atp-minio "http://${MINIO_HOST}:${MINIO_PORT:-9000}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc alias set dr-minio "http://${DR_MINIO_HOST}:${DR_MINIO_PORT:-9000}" "$DR_MINIO_ROOT_USER" "$DR_MINIO_ROOT_PASSWORD"
mc mirror --overwrite --exclude "pg-backups/*" \
  "atp-minio/${MINIO_BUCKET}/" \
  "dr-minio/${DR_MINIO_BUCKET}/atp-objects/"
```

Mirror to a local or mounted directory:

```bash
mc alias set atp-minio "http://${MINIO_HOST}:${MINIO_PORT:-9000}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mirror --overwrite --exclude "pg-backups/*" \
  "atp-minio/${MINIO_BUCKET}/" \
  "/backups/minio/atp-objects/"
```

Verify object backup freshness and size:

```bash
mc ls "dr-minio/${DR_MINIO_BUCKET}/atp-objects/"
mc du "dr-minio/${DR_MINIO_BUCKET}/atp-objects/"
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

## Object Storage Restore

Object storage restore should be rehearsed in a non-production namespace first.
When restoring into production, stop application writes before mirroring objects
back into the primary bucket.

Restore from a remote bucket:

```bash
mc alias set atp-minio "http://${MINIO_HOST}:${MINIO_PORT:-9000}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc alias set dr-minio "http://${DR_MINIO_HOST}:${DR_MINIO_PORT:-9000}" "$DR_MINIO_ROOT_USER" "$DR_MINIO_ROOT_PASSWORD"
mc mirror --overwrite --remove \
  "dr-minio/${DR_MINIO_BUCKET}/atp-objects/" \
  "atp-minio/${MINIO_BUCKET}/"
```

Restore from a local or mounted directory:

```bash
mc alias set atp-minio "http://${MINIO_HOST}:${MINIO_PORT:-9000}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mirror --overwrite --remove \
  "/backups/minio/atp-objects/" \
  "atp-minio/${MINIO_BUCKET}/"
```

After object restore, verify at least one historical screenshot/report/APK
object can be opened from the UI or fetched with a signed URL/API path. Record
the checked object key in `docs/backup-restore-drill-record.md`.

## Kubernetes Drill

1. Scale API and workers down to stop writes:

   ```bash
   kubectl -n atp scale deploy/atp-atp-backend --replicas=0
   kubectl -n atp scale deploy/atp-atp-worker --replicas=0
   kubectl -n atp scale deploy/atp-atp-beat --replicas=0
   ```

2. Run the restore script from an ops image that has `psql`, `gzip`, and `mc`.
   Use the same `POSTGRES_*` and `MINIO_*` values as the ATP release.

3. Restore MinIO application objects from the drill backup target:

   ```bash
   mc mirror --overwrite --remove \
     "dr-minio/${DR_MINIO_BUCKET}/atp-objects/" \
     "atp-minio/${MINIO_BUCKET}/"
   ```

4. Run migrations after restore:

   ```bash
   kubectl -n atp exec deploy/atp-atp-backend -- alembic upgrade head
   ```

5. Scale services back:

   ```bash
   kubectl -n atp scale deploy/atp-atp-backend --replicas=2
   kubectl -n atp scale deploy/atp-atp-worker --replicas=3
   kubectl -n atp scale deploy/atp-atp-beat --replicas=1
   ```

6. Verify:

   ```bash
   curl -fsS https://atp.example.com/health
   kubectl -n atp logs deploy/atp-atp-backend --tail=100
   kubectl -n atp logs deploy/atp-atp-worker --tail=100
   ```

## Drill Checklist

以下勾选项必须来自真实非生产或生产演练记录，不能用本地静态测试代替。
仓库级脚本、文档和 Compose 配置可先用 `make validate-deployment-readiness`
校验；完成 live drill 后，把对象、耗时、迁移、健康检查和 smoke evidence
填写到 `docs/backup-restore-drill-record.md`。
在 Windows 上若没有 Git Bash、WSL 或其他 POSIX shell，校验结果会明确跳过
shell 语法检查；正式演练前应在具备 POSIX shell 的操作员环境中追加
`--require-shell` 执行完整校验。

- [ ] A recent daily backup exists in MinIO.
- [ ] A recent weekly backup exists in MinIO.
- [ ] A recent MinIO application object backup exists outside the primary bucket.
- [ ] Restore script was tested in a non-production namespace.
- [ ] Object storage restore was tested in a non-production namespace.
- [ ] `alembic upgrade head` was run after restore.
- [ ] Backend `/health` returns success after services are restored.
- [ ] A smoke test login and one historical report lookup succeeded.
- [ ] One restored object key was opened or fetched successfully.
- [ ] Drill date, backup object, object backup location, restore duration, and operator were recorded in `docs/backup-restore-drill-record.md`.
