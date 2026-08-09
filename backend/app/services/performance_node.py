"""Node identity, queue dispatch, and node-local performance guardrails."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
import socket
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import settings
from app.models.performance import PerformanceRun, PerformanceRunStatus
from app.services.performance_grpc import GrpcPerformanceOptionsError, target_hostname, validate_grpc_options


class PerformanceNodeConstraintError(ValueError):
    """Raised when a run cannot be executed safely by a selected node."""


def worker_node_id() -> str:
    return (settings.PERFORMANCE_NODE_ID or socket.gethostname()).strip()[:128] or "performance-worker"


def worker_node_name() -> str:
    return (settings.PERFORMANCE_NODE_NAME or worker_node_id()).strip()[:128]


def worker_node_queue() -> str:
    return (settings.PERFORMANCE_NODE_QUEUE or "performance").strip()[:128]


def parse_egress_allowlist(value: str | list[str] | None) -> list[str]:
    values = value.split(",") if isinstance(value, str) else value or []
    return sorted({str(item).strip().lower() for item in values if str(item).strip()})


def _max_vus(options: Mapping[str, Any]) -> int:
    candidates: list[int] = []
    raw_vus = options.get("vus")
    if isinstance(raw_vus, (int, float)):
        candidates.append(int(raw_vus))
    raw_users = options.get("users")
    if isinstance(raw_users, (int, float)):
        candidates.append(int(raw_users))
    raw_concurrency = options.get("concurrency")
    if isinstance(raw_concurrency, (int, float)):
        candidates.append(int(raw_concurrency))
    stages = options.get("stages")
    if isinstance(stages, list):
        for stage in stages:
            if isinstance(stage, dict) and isinstance(stage.get("target"), (int, float)):
                candidates.append(int(stage["target"]))
    scenarios = options.get("scenarios")
    if isinstance(scenarios, dict):
        for scenario in scenarios.values():
            if not isinstance(scenario, dict):
                continue
            for key in ("vus", "vusPerInstance", "maxVUs"):
                value = scenario.get(key)
                if isinstance(value, (int, float)):
                    candidates.append(int(value))
    return max(candidates or [0])


def _target_hosts(options: Mapping[str, Any]) -> set[str]:
    hosts: set[str] = set()
    grpc_host = target_hostname(options.get("target"))
    if grpc_host:
        hosts.add(grpc_host)
    direct_host = options.get("host")
    if isinstance(direct_host, str):
        hostname = urlparse(direct_host).hostname
        if hostname:
            hosts.add(hostname.lower())
    env = options.get("env")
    if isinstance(env, dict):
        for key, value in env.items():
            if str(key).upper() not in {"TARGET_URL", "BASE_URL", "URL"} or not isinstance(value, str):
                continue
            hostname = urlparse(value).hostname
            if hostname:
                hosts.add(hostname.lower())
        raw_rows = env.get("ATP_DATASET_JSON")
        if isinstance(raw_rows, str):
            try:
                rows = json.loads(raw_rows)
            except json.JSONDecodeError:
                rows = []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    for key, value in row.items():
                        if str(key).upper() not in {"TARGET_URL", "BASE_URL", "URL"} or not isinstance(value, str):
                            continue
                        hostname = urlparse(value).hostname
                        if hostname:
                            hosts.add(hostname.lower())
    target_metrics = options.get("target_metrics")
    if isinstance(target_metrics, dict):
        target_url = target_metrics.get("prometheus_url") or target_metrics.get("url")
        target_env_key = target_metrics.get("url_env")
        if not target_url and isinstance(target_env_key, str):
            target_url = env.get(target_env_key) if isinstance(env, dict) else None
            target_url = target_url or os.getenv(target_env_key)
        if isinstance(target_url, str):
            hostname = urlparse(target_url).hostname
            if hostname:
                hosts.add(hostname.lower())
    return hosts


def _host_allowed(host: str, allowlist: set[str]) -> bool:
    return not allowlist or host in allowlist or any(host.endswith(f".{item}") for item in allowlist)


def validate_node_options(options: Mapping[str, Any], node: Any, *, executor: str | None = None) -> None:
    normalized_options: Mapping[str, Any] = options
    if executor == "grpc":
        try:
            normalized_options = validate_grpc_options(options)
        except GrpcPerformanceOptionsError as exc:
            raise PerformanceNodeConstraintError(str(exc)) from exc
    max_vus = getattr(node, "max_vus", None) or 0
    requested_vus = _max_vus(normalized_options)
    if max_vus > 0 and requested_vus > max_vus:
        raise PerformanceNodeConstraintError(f"压测 VUs 超过节点 {getattr(node, 'name', 'selected')} 限制 {max_vus}")

    allowlist = set(parse_egress_allowlist(getattr(node, "egress_allowlist", [])))
    blocked = sorted(host for host in _target_hosts(normalized_options) if not _host_allowed(host, allowlist))
    if blocked:
        raise PerformanceNodeConstraintError(
            f"压测目标域名不在节点 {getattr(node, 'name', 'selected')} 网络出口 allowlist: {', '.join(blocked)}"
        )


def effective_node_status(node: Any, now=None) -> str:
    if not getattr(node, "enabled", False):
        return "disabled"
    stored_status = str(getattr(node, "status", "offline"))
    if stored_status == "draining":
        return stored_status
    heartbeat = getattr(node, "last_heartbeat_at", None)
    if heartbeat is None:
        return "offline"
    from datetime import datetime, timezone

    current = now or datetime.now(timezone.utc)
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=timezone.utc)
    age = (current - heartbeat).total_seconds()
    return "online" if age <= settings.PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS else "offline"


async def active_run_count(db: Any, node_id: int, *, exclude_run_id: int | None = None) -> int:
    """Count runs currently consuming a node's execution capacity."""
    statement = select(PerformanceRun.id).where(
        PerformanceRun.performance_node_id == node_id,
        PerformanceRun.status.in_(
            [
                PerformanceRunStatus.pending.value,
                PerformanceRunStatus.running.value,
                PerformanceRunStatus.cancelling.value,
            ]
        ),
    )
    if exclude_run_id is not None:
        statement = statement.where(PerformanceRun.id != exclude_run_id)
    result = await db.execute(statement)
    return len(result.scalars().all())


async def node_has_capacity(db: Any, node: Any, *, exclude_run_id: int | None = None) -> bool:
    limit = getattr(node, "max_concurrency", None)
    return not limit or await active_run_count(db, node.id, exclude_run_id=exclude_run_id) < limit


def enqueue_performance_run(task: Any, run_id: int, queue_name: str | None = None) -> None:
    """Route a run to a node queue while keeping the default task contract intact."""
    if queue_name and hasattr(task, "apply_async"):
        task.apply_async(args=(run_id,), queue=queue_name)
    else:
        task.delay(run_id)
