#!/bin/sh
# ATP PostgreSQL restore script.
#
# This script restores a gzip-compressed plain SQL dump produced by
# scripts/backup-postgres.sh. It intentionally requires an explicit danger
# flag because it drops and recreates the target database.
#
# Usage:
#   restore-postgres.sh --i-know-this-overwrites --file /backup/atp.sql.gz
#   restore-postgres.sh --i-know-this-overwrites --object pg-backups/daily/atp-20260528-010000.sql.gz
#
# Required environment:
#   POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
#   MINIO_HOST / MINIO_PORT / MINIO_ROOT_USER / MINIO_ROOT_PASSWORD / MINIO_BUCKET

set -eu

CONFIRM=""
SOURCE_FILE=""
SOURCE_OBJECT=""

usage() {
  echo "Usage:"
  echo "  $0 --i-know-this-overwrites --file /path/to/atp.sql.gz"
  echo "  $0 --i-know-this-overwrites --object pg-backups/daily/atp-YYYYMMDD-HHMMSS.sql.gz"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --i-know-this-overwrites)
      CONFIRM="yes"
      shift
      ;;
    --file)
      SOURCE_FILE="${2:-}"
      shift 2
      ;;
    --object)
      SOURCE_OBJECT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[restore] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$CONFIRM" != "yes" ]; then
  echo "[restore] missing required flag: --i-know-this-overwrites" >&2
  exit 2
fi

if [ -n "$SOURCE_FILE" ] && [ -n "$SOURCE_OBJECT" ]; then
  echo "[restore] choose only one source: --file or --object" >&2
  exit 2
fi

if [ -z "$SOURCE_FILE" ] && [ -z "$SOURCE_OBJECT" ]; then
  echo "[restore] missing source: --file or --object" >&2
  usage >&2
  exit 2
fi

case "$POSTGRES_DB" in
  *[!A-Za-z0-9_.-]*|"")
    echo "[restore] POSTGRES_DB contains unsupported characters" >&2
    exit 2
    ;;
esac

case "$POSTGRES_USER" in
  *[!A-Za-z0-9_.-]*|"")
    echo "[restore] POSTGRES_USER contains unsupported characters" >&2
    exit 2
    ;;
esac

TMP_FILE="$(mktemp -t atp-pg-restore.XXXXXX.sql.gz)"
trap 'rm -f "$TMP_FILE"' EXIT INT TERM

if [ -n "$SOURCE_OBJECT" ]; then
  echo "[restore] downloading object: ${SOURCE_OBJECT}"
  mc alias set atp-minio "http://${MINIO_HOST}:${MINIO_PORT:-9000}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
  mc cp "atp-minio/${MINIO_BUCKET}/${SOURCE_OBJECT}" "$TMP_FILE"
  RESTORE_FILE="$TMP_FILE"
else
  if [ ! -f "$SOURCE_FILE" ]; then
    echo "[restore] file not found: $SOURCE_FILE" >&2
    exit 2
  fi
  RESTORE_FILE="$SOURCE_FILE"
fi

case "$RESTORE_FILE" in
  *.gz) ;;
  *)
    echo "[restore] expected a .sql.gz dump: $RESTORE_FILE" >&2
    exit 2
    ;;
esac

echo "[restore] target db=${POSTGRES_DB} host=${POSTGRES_HOST}:${POSTGRES_PORT:-5432}"
echo "[restore] dropping and recreating database"

export PGPASSWORD="$POSTGRES_PASSWORD"

psql \
  -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" -d postgres \
  -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"${POSTGRES_DB}\";" \
  -c "CREATE DATABASE \"${POSTGRES_DB}\" OWNER \"${POSTGRES_USER}\";"

echo "[restore] loading dump"
gzip -dc "$RESTORE_FILE" | psql \
  -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1

echo "[restore] done"
