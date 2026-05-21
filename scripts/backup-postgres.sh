#!/bin/sh
# ATP PostgreSQL 备份脚本：pg_dump → gzip → MinIO
#
# 环境变量（容器内通常已通过 envFrom 注入）：
#   POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
#   MINIO_HOST / MINIO_PORT / MINIO_ROOT_USER / MINIO_ROOT_PASSWORD / MINIO_BUCKET
#   BACKUP_KIND=daily|weekly  控制写入 prefix
#
# 输出对象名：pg-backups/{KIND}/atp-YYYYMMDD-HHMMSS.sql.gz

set -eu

KIND="${BACKUP_KIND:-daily}"
TS="$(date -u +%Y%m%d-%H%M%S)"
FILE="atp-${TS}.sql.gz"
OBJECT="pg-backups/${KIND}/${FILE}"
TMP_FILE="$(mktemp -t atp-pg-backup.XXXXXX.sql.gz)"
trap 'rm -f "$TMP_FILE"' EXIT INT TERM

echo "[backup] start: kind=$KIND db=$POSTGRES_DB host=$POSTGRES_HOST target=$OBJECT"

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump \
  -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=plain --no-owner --no-acl \
  | gzip -9 > "$TMP_FILE"

SIZE="$(wc -c < "$TMP_FILE")"
echo "[backup] dumped size=${SIZE}B"

# 上传 MinIO（使用 mc 或 awscli 兼容客户端）
# 这里给出 mc 写法；运维侧可替换为 awscli s3 cp
mc alias set atp-minio "http://${MINIO_HOST}:${MINIO_PORT:-9000}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc cp "$TMP_FILE" "atp-minio/${MINIO_BUCKET}/${OBJECT}"

echo "[backup] uploaded: ${OBJECT}"
echo "[backup] done"
