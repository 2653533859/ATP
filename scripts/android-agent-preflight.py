"""Read-only M0 inventory. No screenshots, device writes, or model calls."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess


def inspect_environment(adb: str, database: Path | None) -> dict:
    report = {"schema_version": 1, "checked_at": datetime.now(timezone.utc).isoformat(), "checks": {}}
    checks = report["checks"]
    try:
        result = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            checks["adb"] = {"status": "blocked", "reason": "adb_failed"}
        else:
            # Report counts only: do not persist device serials or LAN addresses.
            states = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] in {"device", "offline", "unauthorized"}:
                    states.append(parts[1])
            checks["adb"] = {
                "status": "ready" if "device" in states else "blocked",
                "online": states.count("device"),
                "offline": states.count("offline"),
                "unauthorized": states.count("unauthorized"),
            }
    except (OSError, subprocess.TimeoutExpired):
        checks["adb"] = {"status": "blocked", "reason": "adb_unavailable"}
    if database is None:
        checks["model_config"] = {"status": "unverified", "reason": "database_not_supplied"}
    else:
        try:
            # mode=ro also prevents an incorrect path from silently creating a DB.
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=3) as connection:
                count = connection.execute(
                    "SELECT count(*) FROM ai_llm_configs WHERE enabled=1 AND supports_vision=1"
                ).fetchone()[0]
            checks["model_config"] = {
                "status": "configured" if count else "blocked",
                "enabled_vision_models": count,
                "model_call_verified": False,
            }
        except sqlite3.Error:
            checks["model_config"] = {"status": "blocked", "reason": "database_unavailable_or_incompatible"}
    # Inventory is never sufficient to close M0, even with a connected device.
    checks["test_app"] = {"status": "unverified"}
    checks["model_image_permission"] = {"status": "unverified"}
    report["m0_accepted"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--database", type=Path, help="Optional existing local ATP SQLite database (read-only)")
    parser.add_argument("--output", type=Path, help="Write a new sanitized JSON report; refuses overwrite")
    args = parser.parse_args()
    report = inspect_environment(args.adb, args.database)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    print(rendered)
    return 2 if any(x["status"] == "blocked" for x in report["checks"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
