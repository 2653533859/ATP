#!/usr/bin/env bash
# ATP Android ADB-over-TCP 诊断脚本
# Usage: bash scripts/android-network-doctor.sh [HOST:PORT]
# 默认 HOST:PORT = 127.0.0.1:5555
# ADB_SKIP_SERVER_RESTART=true: 复用外部 ADB server 时不执行 kill/start-server
# ADB_SKIP_CONNECT=true: target 已由共享 ADB server 维护时跳过 adb connect

set -u

TARGET="${1:-127.0.0.1:5555}"
FAILED=0

ok()   { echo "[OK]   $*"; }
fail() { echo "[FAIL] $*"; FAILED=1; }

echo "=== ATP Android Network Doctor ==="
echo "Target: $TARGET"
echo

# 1. adb 可执行
ADB_PATH="$(command -v adb || true)"
if [[ -z "$ADB_PATH" ]]; then
  fail "adb binary not found in PATH"
  echo "Hint: install Android Platform Tools and ensure adb is in PATH"
  exit 1
fi
ok "adb binary found: $ADB_PATH"

# 2. 重启 adb server（共享宿主 ADB server 时必须跳过，避免终止宿主服务）
if [[ "${ADB_SKIP_SERVER_RESTART:-false}" == "true" ]]; then
  ok "adb server restart skipped"
elif adb kill-server >/dev/null 2>&1 && adb start-server >/dev/null 2>&1; then
  ok "adb server restarted"
else
  fail "adb server restart failed"
  echo "Hint: check adb permissions or other running adb processes"
fi

# 3. 连接 target（共享 server 已维护 serial 时可跳过）
if [[ "${ADB_SKIP_CONNECT:-false}" == "true" ]]; then
  ok "connect skipped for existing serial: $TARGET"
else
  CONNECT_OUT="$(adb connect "$TARGET" 2>&1)"
  if echo "$CONNECT_OUT" | grep -qiE "connected|already connected"; then
    ok "connect $TARGET"
  else
    fail "connect $TARGET: $CONNECT_OUT"
    echo "Hint: check device IP/port, firewall (5555/tcp), and that 'adb tcpip 5555' ran on device first"
  fi
fi

# 4. 设备列表
DEVICES_OUT="$(adb devices 2>&1)"
if echo "$DEVICES_OUT" | grep -q "${TARGET}[[:space:]]\+device"; then
  ok "device listed: $TARGET  device"
elif echo "$DEVICES_OUT" | grep -q "${TARGET}[[:space:]]\+offline"; then
  fail "device offline"
  echo "Hint: try 'adb disconnect $TARGET && adb connect $TARGET'; or wake the device screen"
elif echo "$DEVICES_OUT" | grep -q "${TARGET}[[:space:]]\+unauthorized"; then
  fail "device unauthorized"
  echo "Hint: USB-connect once and tap 'Allow USB debugging' on the device"
else
  fail "device not in 'adb devices' list"
  echo "--- adb devices output ---"
  echo "$DEVICES_OUT"
  echo "--------------------------"
fi

# 5. shell echo 探活
if SHELL_OUT="$(adb -s "$TARGET" shell 'echo ok' 2>&1)"; then
  if [[ "$(echo "$SHELL_OUT" | tr -d '\r\n')" == "ok" ]]; then
    ok "shell echo: ok"
  else
    fail "shell echo returned: $SHELL_OUT"
  fi
else
  fail "shell command failed: $SHELL_OUT"
fi

echo
if [[ $FAILED -eq 0 ]]; then
  echo "All checks passed."
  exit 0
else
  echo "One or more checks failed; see hints above."
  exit 1
fi
