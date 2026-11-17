#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PS_SCRIPT="$SCRIPT_DIR/deploy-linux.ps1"

if command -v cygpath >/dev/null 2>&1; then
    PS_SCRIPT="$(cygpath -w "$PS_SCRIPT")"
fi

if command -v powershell.exe >/dev/null 2>&1; then
    exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS_SCRIPT" "$@"
elif command -v pwsh >/dev/null 2>&1; then
    exec pwsh -NoProfile -ExecutionPolicy Bypass -File "$PS_SCRIPT" "$@"
else
    echo "[deploy-linux] Neither powershell.exe nor pwsh is available on this system." >&2
    exit 1
fi
