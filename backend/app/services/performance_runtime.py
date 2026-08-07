"""Shared option snapshot helpers for manual and scheduled performance runs."""

from __future__ import annotations

from app.core.encryption import encrypt
from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY


def merge_options(default_options: dict | None, override: dict | None) -> dict:
    merged = dict(default_options or {})
    merged.update(override or {})
    env = dict((default_options or {}).get("env") or {})
    env.update((override or {}).get("env") or {})
    if env:
        merged["env"] = env
    return merged


def build_options_snapshot(
    default_options: dict | None,
    override: dict | None,
    environment_values: dict,
    secret_keys: set[str],
) -> tuple[dict, dict]:
    """Return a safe persisted snapshot and the full runtime options."""
    snapshot = merge_options(default_options, override)
    snapshot_env = dict(snapshot.get("env") or {})
    for key in environment_values:
        snapshot_env.pop(key, None)
    for key in secret_keys:
        snapshot_env.pop(key, None)
    if snapshot_env:
        snapshot["env"] = snapshot_env
    else:
        snapshot.pop("env", None)

    runtime = dict(snapshot)
    runtime_env = dict(environment_values)
    runtime_env.update(snapshot_env)
    if runtime_env:
        runtime["env"] = runtime_env
    if environment_values:
        snapshot[ENVIRONMENT_SNAPSHOT_KEY] = {key: encrypt(str(value)) for key, value in environment_values.items()}
    return snapshot, runtime
