#!/bin/sh
set -eu

mode="${1:-serve}"

case "$mode" in
  migrate)
    shift
    if [ "$#" -ne 0 ]; then
      echo "migrate does not accept additional arguments" >&2
      exit 64
    fi
    exec python -m app.migration_startup
    ;;
  serve)
    shift
    skip_migrations=false
    if [ "${1:-}" = "--skip-migrations" ]; then
      skip_migrations=true
      shift
    fi
    if [ "$#" -ne 0 ]; then
      echo "serve only accepts --skip-migrations" >&2
      exit 64
    fi
    if [ "$skip_migrations" = false ]; then
      python -m app.migration_startup
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  *)
    exec "$@"
    ;;
esac
