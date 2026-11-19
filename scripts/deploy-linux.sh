#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PS_SCRIPT="$SCRIPT_DIR/deploy-linux.ps1"

HOOK_MODE=0
for arg in "$@"; do
    case "$arg" in
        -HookMode|-hookmode|--hook-mode)
            HOOK_MODE=1
            ;;
    esac
done

if [ "$HOOK_MODE" = "1" ]; then
    case "${ATP_SKIP_DEPLOY:-${SKIP_DEPLOY:-}}" in
        1|true|TRUE|yes|YES)
            echo "[deploy-linux] ATP_SKIP_DEPLOY detected; skipping Linux server deployment."
            exit 0
            ;;
    esac
fi

if command -v cygpath >/dev/null 2>&1; then
    PS_SCRIPT="$(cygpath -w "$PS_SCRIPT")"
fi

if command -v powershell.exe >/dev/null 2>&1; then
    exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS_SCRIPT" "$@"
elif command -v pwsh >/dev/null 2>&1; then
    exec pwsh -NoProfile -ExecutionPolicy Bypass -File "$PS_SCRIPT" "$@"
else
    if [ "$HOOK_MODE" = "1" ]; then
        echo "[deploy-linux] WARN: PowerShell (pwsh) not installed; skipping automatic Linux deploy hook." >&2
        exit 0
    fi
    echo "[deploy-linux] Neither powershell.exe nor pwsh is available on this system." >&2
    exit 1
fi
