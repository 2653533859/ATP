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

## Current single-node acceptance boundary

The 2026-09-10 C1.3 drill enabled scheduled PostgreSQL backup on
`atp-single-node`, executed the real Celery maintenance task, and restored its
MinIO object into an isolated database. It also restored an RDB snapshot in an
isolated Redis container and verified a same-endpoint MinIO object round trip.
See [`c1-data-services-recovery-2026-09-10.json`](evidence/c1-data-services-recovery-2026-09-10.json).

The 2026-09-12 C3.2 rollout closed the application-credential portion of that
audit on the target single node. PostgreSQL now separates an unmounted
bootstrap operator, a non-superuser migration owner and a DML-only runtime
role; Redis uses a persisted restricted ACL user; MinIO uses a bucket-scoped
application principal. The real Celery daily backup and a post-restart
40-second stability sample passed. See
[`c3-least-privilege-2026-09-12.json`](evidence/c3-least-privilege-2026-09-12.json).

The 2026-09-12 C3.3 drill then exercised an empty database, a one-revision
upgrade/downgrade/re-upgrade cycle and the latest daily backup in isolated
databases. It found that a structurally valid `--no-acl` restore did not grant
the runtime role access. Revision `6755ed9f` makes every online Alembic run
reconcile existing and default runtime grants. The post-fix restore passed with
runtime DML and sequence access while schema `CREATE` remained denied. See
[`c3-migration-restore-2026-09-12.json`](evidence/c3-migration-restore-2026-09-12.json).

The 2026-09-13 C3.4.1 change enabled Redis AOF with `appendfsync everysec` and
an RDB preamble. An isolated clone first proved that the RDB must be loaded
before enabling AOF online; starting an existing RDB clone directly with AOF
enabled selected an empty AOF data set. The accepted sequence survived a live
Compose recreation and a second Redis restart. The same change enabled MinIO
bucket versioning and verified two object versions, a delete marker, historical
read and complete probe cleanup. See
[`c3-release-observability-data-governance-2026-09-13.json`](evidence/c3-release-observability-data-governance-2026-09-13.json).

The following boundaries still prevent a production DR claim:

- Redis AOF every-second persistence reduces the control-plane RPO but does not
  make Redis authoritative or protect against loss of the single host. Keep RDB
  snapshots and verify both AOF and RDB status after every Redis change.
- A dump stored in MinIO on the same host protects against logical database
  loss only; it does not protect against host or primary-object-store loss.
- MinIO versioning protects overwrites and delete-marker mistakes on the same
  endpoint. Automatic lifecycle expiration is intentionally not configured
  until prefixes are reviewed against database references. An independent
  backup endpoint remains required; same-host versioning is not DR.

Use `POSTGRES_MIGRATION_USER`/`POSTGRES_MIGRATION_PASSWORD` only for schema
migrations and keep them out of long-running application Pods. Backups and
restores need a separately reviewed operator identity with the required dump,
database-create and object permissions; do not broaden the ATP runtime role to
make a recovery command convenient.

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

The latest target change is recorded in
`docs/evidence/c3-release-observability-data-governance-2026-09-13.json`.
Versioning is enabled, while the bucket still has no lifecycle rule because it
contains objects covered by database retention/reference policies. Do not turn
that deliberate absence into a blanket root-prefix expiration rule.

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

## Cross-endpoint MinIO recovery smoke

For a repeatable non-production drill, use `scripts/minio-dr-acceptance.py`.
It requires separate source and target MinIO endpoints on different hosts,
rejects same-host aliases (including loopback aliases) or endpoints that
resolve to the same IP, and reads all access keys from environment variables. The command copies a
uniquely scoped probe object to the
target, reads it back, restores it to a new source object, compares SHA-256 at
each boundary, and removes the temporary objects.

```bash
export ATP_MINIO_DR_SOURCE_ENDPOINT=primary.example.test:9000
export ATP_MINIO_DR_SOURCE_ACCESS_KEY="由安全渠道注入"
export ATP_MINIO_DR_SOURCE_SECRET_KEY="由安全渠道注入"
export ATP_MINIO_DR_SOURCE_BUCKET=atp
export ATP_MINIO_DR_TARGET_ENDPOINT=backup.example.test:9000
export ATP_MINIO_DR_TARGET_ACCESS_KEY="由安全渠道注入"
export ATP_MINIO_DR_TARGET_SECRET_KEY="由安全渠道注入"
export ATP_MINIO_DR_TARGET_BUCKET=atp-dr

make minio-dr-acceptance \
  ARGS='--report docs/evidence/minio-dr-acceptance-YYYY-MM-DD.json'
```

如需把生命周期规则纳入发布门禁，可重复传入 `--require-lifecycle-rule
PREFIX=DAYS`；两端都必须存在 `Enabled` 且前缀、过期天数精确匹配的规则：

```bash
python scripts/minio-dr-acceptance.py \
  --report docs/evidence/minio-dr-acceptance-YYYY-MM-DD.json \
  --require-lifecycle-rule 'tmp/=7'
```

没有独立目标主机时不要把同一 MinIO 或同一主机的不同 bucket 记录为跨主机恢复通过；
该命令会拒绝相同主机。完成 live drill 后，把报告路径、对象前缀、耗时和
恢复后的业务对象检查结果记录到 `docs/backup-restore-drill-record.md`。

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

4. Run migrations after restore through the release's pre-upgrade Hook. The
   long-running Backend Pod intentionally does not mount the migration Secret,
   so do not run Alembic with `kubectl exec` there:

   ```bash
   helm upgrade atp deploy/helm/atp \
     -n atp \
     -f production-values.yaml \
     --reuse-values \
     --rollback-on-failure \
     --wait
   ```

   Confirm `migrationSecret.existingName` still names the dedicated migration
   Secret before running the command. The Hook also reconciles the separated
   runtime role's current and default grants. Verify the application role can
   query a business table and cannot create objects in `public`; checking only
   the Alembic version is insufficient.

5. Confirm Helm restored the desired replicas and every rollout completed:

   ```bash
   kubectl -n atp rollout status deploy/atp-atp-backend
   kubectl -n atp rollout status deploy/atp-atp-worker
   kubectl -n atp rollout status deploy/atp-atp-beat
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
