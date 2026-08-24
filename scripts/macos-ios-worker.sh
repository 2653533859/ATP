#!/bin/sh
# macOS iOS/Appium Worker preflight and launcher.
# This worker only consumes the iOS queue; it never starts ADB or performance work.

set -eu

ACTION="${1:-doctor}"
PYTHON_BIN="${ATP_PYTHON:-python3}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[FAIL] missing command: $1" >&2
    return 1
  }
}

doctor() {
  require_command "$PYTHON_BIN"
  "$PYTHON_BIN" -c 'import celery' >/dev/null 2>&1 || {
    echo "[FAIL] Python environment does not contain Celery" >&2
    return 1
  }
  require_command appium
  require_command xcodebuild
  require_command xcrun

  appium driver list --installed 2>/dev/null | grep -qi 'xcuitest' || {
    echo "[FAIL] Appium XCUITest driver is not installed" >&2
    return 1
  }
  xcodebuild -version | sed -n '1,2p'
  printf '%s\n' '[PASS] macOS/Xcode/Appium/XCUITest prerequisites are ready'
  printf '%s\n' '[INFO] available simulators:'
  xcrun simctl list devices available | sed -n '1,24p'
}

case "$ACTION" in
  doctor)
    doctor
    ;;
  start)
    doctor
    # Do not allow a copied general-purpose env file to make this worker
    # consume Android, maintenance, or performance tasks.
    export CELERY_QUEUES=ios
    exec "$PYTHON_BIN" -m celery -A app.worker.celery_app worker --loglevel=info --pool=solo -Q "$CELERY_QUEUES"
    ;;
  *)
    echo "usage: $0 {doctor|start}" >&2
    exit 2
    ;;
esac
