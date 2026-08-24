#!/usr/bin/env python3
"""Validate the paired ATP Backend and Windows Android Worker environments.

The Backend and Agent must use the same PostgreSQL, Redis, MinIO and encryption
identity, while their ADB modes and Celery queues must remain different. This
check reports only key names and queue/mode values; it never prints secret
values or writes them to the JSON report.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys


ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ANDROID_QUEUES = {"android", "mobile_special"}
AGENT_QUEUES = {"android", "mobile_special"}
SHARED_KEYS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "MINIO_HOST",
    "MINIO_PORT",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "MINIO_BUCKET",
    "APP_SECRET_KEY",
    "ENCRYPTION_KEY",
)


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def read_env(path: Path) -> dict[str, str]:
    """Read simple dotenv assignments without expanding or exposing values."""

    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{path.name}:{number}: expected KEY=value")
        key, value = line.split("=", 1)
        key = key.strip()
        if not ENV_KEY.fullmatch(key):
            raise ValueError(f"{path.name}:{number}: invalid environment key")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _queues(values: dict[str, str]) -> set[str]:
    return {item.strip().lower() for item in values.get("CELERY_QUEUES", "").split(",") if item.strip()}


def validate_profiles(backend: dict[str, str], agent: dict[str, str]) -> list[Check]:
    checks: list[Check] = []
    for key in SHARED_KEYS:
        backend_value = backend.get(key, "")
        agent_value = agent.get(key, "")
        checks.append(
            Check(
                name=f"shared {key}",
                passed=key in backend and key in agent and backend_value == agent_value,
                detail="values match"
                if key in backend and key in agent and backend_value == agent_value
                else "missing or differs",
            )
        )

    backend_queues = _queues(backend)
    agent_queues = _queues(agent)
    checks.extend(
        (
            Check(
                "backend ADB scan mode",
                backend.get("ADB_SCAN_MODE", "").strip().lower() == "worker",
                "worker" if backend.get("ADB_SCAN_MODE", "").strip().lower() == "worker" else "must be worker",
            ),
            Check(
                "agent ADB scan mode",
                agent.get("ADB_SCAN_MODE", "").strip().lower() == "local",
                "local" if agent.get("ADB_SCAN_MODE", "").strip().lower() == "local" else "must be local",
            ),
            Check(
                "backend Android queues excluded",
                not backend_queues.intersection(ANDROID_QUEUES),
                "android queues excluded"
                if not backend_queues.intersection(ANDROID_QUEUES)
                else "must exclude android,mobile_special",
            ),
            Check(
                "agent queue set",
                agent_queues == AGENT_QUEUES,
                "android,mobile_special" if agent_queues == AGENT_QUEUES else "must be android,mobile_special",
            ),
            Check(
                "Android worker queue",
                backend.get("ANDROID_WORKER_QUEUE", "") == agent.get("ANDROID_WORKER_QUEUE", "") == "mobile_special",
                "mobile_special"
                if backend.get("ANDROID_WORKER_QUEUE") == agent.get("ANDROID_WORKER_QUEUE") == "mobile_special"
                else "must match mobile_special",
            ),
            Check(
                "Android registry prefix",
                bool(backend.get("ANDROID_WORKER_REGISTRY_PREFIX"))
                and backend.get("ANDROID_WORKER_REGISTRY_PREFIX") == agent.get("ANDROID_WORKER_REGISTRY_PREFIX"),
                "values match"
                if backend.get("ANDROID_WORKER_REGISTRY_PREFIX") == agent.get("ANDROID_WORKER_REGISTRY_PREFIX")
                else "missing or differs",
            ),
            Check(
                "ADB scan enabled",
                backend.get("ADB_SCAN_ENABLED", "").strip().lower() in {"1", "true", "yes"}
                and agent.get("ADB_SCAN_ENABLED", "").strip().lower() in {"1", "true", "yes"},
                "enabled"
                if backend.get("ADB_SCAN_ENABLED", "").strip().lower() in {"1", "true", "yes"}
                and agent.get("ADB_SCAN_ENABLED", "").strip().lower() in {"1", "true", "yes"}
                else "both profiles must enable ADB",
            ),
        )
    )
    return checks


def _report(checks: list[Check], backend_path: Path, agent_path: Path) -> dict:
    return {
        "schema_version": 1,
        "kind": "android_worker_config_pair",
        "status": "passed" if all(item.passed for item in checks) else "failed",
        "backend_profile": backend_path.name,
        "agent_profile": agent_path.name,
        "checks": [{"name": item.name, "passed": item.passed, "detail": item.detail} for item in checks],
        "credential_values_recorded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-env", type=Path, required=True, help="Backend deployment environment file")
    parser.add_argument("--agent-env", type=Path, required=True, help="Windows Android Agent environment file")
    parser.add_argument("--report", type=Path, help="Optional redacted JSON report path")
    args = parser.parse_args()

    try:
        backend = read_env(args.backend_env)
        agent = read_env(args.agent_env)
    except (OSError, ValueError) as exc:
        print(f"[FAIL] unable to read configuration: {exc}", file=sys.stderr)
        return 2

    checks = validate_profiles(backend, agent)
    report = _report(checks, args.backend_env, args.agent_env)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for item in checks:
        prefix = "[PASS]" if item.passed else "[FAIL]"
        print(f"{prefix} {item.name}: {item.detail}")
    if not all(item.passed for item in checks):
        return 1
    print("[PASS] Android Backend/Agent configuration pair is aligned; values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
