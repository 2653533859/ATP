"""Unified, safe diagnostics for remote infrastructure and execution workers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_engineer
from app.api.v1.health import _probe_minio, _probe_postgres, _probe_redis
from app.core.config import settings
from app.core.database import get_db
from app.models.performance_node import PerformanceNode
from app.schemas.remote_toolbox import (
    RemoteToolboxCheck,
    RemoteToolboxOverview,
    RemoteToolboxResource,
)
from app.services.android_worker_registry import AndroidWorkerRegistryError, list_android_workers
from app.services.performance_node import effective_node_status
from app.services.web_recording_transport import WebRecordingTransportError, list_recording_workers

router = APIRouter(prefix="/remote-toolbox", tags=["远程工具箱"])


def _message(code: str) -> str:
    return {
        "ok": "连接正常",
        "timeout": "连接超时",
        "unreachable": "服务不可达",
        "bucket_missing": "MinIO 存储桶不存在",
        "online": "存在可用节点",
        "local_mode": "Web 录制使用本地模式",
        "no_worker": "没有在线 Worker",
        "adb_ready": "ADB 能力已注册",
        "adb_capability_missing": "在线 Worker 未声明 ADB 能力",
        "registry_unreachable": "Worker 注册中心不可用",
        "no_node": "没有注册性能节点",
        "no_online_node": "没有在线性能节点",
        "database_unreachable": "性能节点数据不可读取",
    }.get(code, "检查未通过")


def _check(
    *,
    key: str,
    category: str,
    status: str,
    code: str,
    started: float,
    resources: list[RemoteToolboxResource] | None = None,
) -> RemoteToolboxCheck:
    return RemoteToolboxCheck(
        key=key,
        category=category,
        status=status,
        code=code,
        latency_ms=round((perf_counter() - started) * 1000, 1),
        resources=resources or [],
    )


def _dependency_check(key: str, item: Any) -> RemoteToolboxCheck:
    code = str(item.code)
    return RemoteToolboxCheck(
        key=key,
        category="infrastructure",
        status="ok" if item.status == "ok" else "error",
        code=code,
        latency_ms=float(item.latency_ms),
        resources=[
            RemoteToolboxResource(
                id=key,
                name=key,
                status="ok" if item.status == "ok" else "error",
                summary=_message(code),
            )
        ],
    )


def _safe_performance_capabilities(value: Any) -> dict[str, list[str]]:
    """Keep the diagnostics contract limited to non-sensitive executor names."""

    if not isinstance(value, dict):
        return {}
    raw_executors = value.get("executors")
    if not isinstance(raw_executors, (list, tuple, set)):
        return {}
    executors = [item.strip() for item in raw_executors if isinstance(item, str) and item.strip()]
    return {"executors": executors} if executors else {}


def _android_checks(workers: list[dict[str, Any]], started: float) -> list[RemoteToolboxCheck]:
    resources = [
        RemoteToolboxResource(
            id=str(worker.get("worker_id") or "unknown"),
            name=str(worker.get("worker_id") or "Android Worker"),
            status="ok",
            summary="在线",
            metadata={
                "queues": [str(item) for item in worker.get("queues", []) if item],
                "capabilities": [str(item) for item in worker.get("capabilities", []) if item],
            },
        )
        for worker in workers
    ]
    worker_status = "ok" if workers else "warning"
    worker_code = "online" if workers else "no_worker"
    adb_ready = any("adb" in {str(item).lower() for item in worker.get("capabilities", [])} for worker in workers)
    adb_status = "ok" if adb_ready else "warning"
    adb_code = "adb_ready" if adb_ready else "no_worker" if not workers else "adb_capability_missing"
    return [
        _check(
            key="android_worker",
            category="execution",
            status=worker_status,
            code=worker_code,
            started=started,
            resources=resources,
        ),
        _check(
            key="adb",
            category="execution",
            status=adb_status,
            code=adb_code,
            started=started,
            resources=resources if adb_ready else [],
        ),
    ]


async def _load_android_checks() -> list[RemoteToolboxCheck]:
    started = perf_counter()
    try:
        workers = await list_android_workers()
    except AndroidWorkerRegistryError:
        return [
            _check(
                key="android_worker",
                category="execution",
                status="error",
                code="registry_unreachable",
                started=started,
            ),
            _check(
                key="adb",
                category="execution",
                status="error",
                code="registry_unreachable",
                started=started,
            ),
        ]
    return _android_checks(workers, started)


async def _load_web_check() -> RemoteToolboxCheck:
    started = perf_counter()
    if settings.WEB_RECORDER_MODE.strip().lower() != "worker":
        return _check(
            key="web_worker",
            category="execution",
            status="ok",
            code="local_mode",
            started=started,
        )
    try:
        workers = await list_recording_workers()
    except WebRecordingTransportError:
        return _check(
            key="web_worker",
            category="execution",
            status="error",
            code="registry_unreachable",
            started=started,
        )
    resources: list[RemoteToolboxResource] = []
    available = 0
    for worker in workers:
        try:
            active = max(0, int(worker.get("active_sessions", 0)))
            capacity = max(1, int(worker.get("capacity", 1)))
        except (TypeError, ValueError):
            active, capacity = 0, 1
        is_available = active < capacity
        available += int(is_available)
        resources.append(
            RemoteToolboxResource(
                id=str(worker.get("worker_id") or "unknown"),
                name=str(worker.get("worker_id") or "Web Worker"),
                status="ok" if is_available else "warning",
                summary=f"可用 {max(0, capacity - active)}/{capacity}",
                metadata={"active_sessions": active, "capacity": capacity},
            )
        )
    code = "online" if available else "no_worker"
    return _check(
        key="web_worker",
        category="execution",
        status="ok" if available else "warning",
        code=code,
        started=started,
        resources=resources,
    )


async def _load_performance_check(db: AsyncSession) -> RemoteToolboxCheck:
    started = perf_counter()
    try:
        result = await db.execute(select(PerformanceNode).order_by(PerformanceNode.name.asc()))
        nodes = result.scalars().all()
    except Exception:
        return _check(
            key="performance_node",
            category="execution",
            status="error",
            code="database_unreachable",
            started=started,
        )
    resources = [
        RemoteToolboxResource(
            id=str(node.node_id),
            name=node.name,
            status="ok" if effective_node_status(node) == "online" else "warning",
            summary=effective_node_status(node),
            metadata={
                "queue_name": node.queue_name,
                "capabilities": _safe_performance_capabilities(node.capabilities),
                "last_heartbeat_at": node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None,
            },
        )
        for node in nodes
    ]
    online = sum(1 for item in resources if item.status == "ok")
    code = "online" if online else "no_node" if not resources else "no_online_node"
    return _check(
        key="performance_node",
        category="execution",
        status="ok" if online else "warning",
        code=code,
        started=started,
        resources=resources,
    )


@router.get("/overview", response_model=RemoteToolboxOverview)
async def get_remote_toolbox_overview(
    db: AsyncSession = Depends(get_db),
    _engineer=Depends(require_engineer),
) -> RemoteToolboxOverview:
    postgres, redis, minio, android_checks, web_check, performance_check = await asyncio.gather(
        _probe_postgres(),
        _probe_redis(),
        _probe_minio(),
        _load_android_checks(),
        _load_web_check(),
        _load_performance_check(db),
    )
    checks = [
        _dependency_check("postgres", postgres),
        _dependency_check("redis", redis),
        _dependency_check("minio", minio),
        *android_checks,
        web_check,
        performance_check,
    ]
    checked_at = datetime.now(timezone.utc)
    if any(item.status == "error" for item in checks):
        overall = "error"
    elif any(item.status == "warning" for item in checks):
        overall = "degraded"
    else:
        overall = "ok"
    return RemoteToolboxOverview(status=overall, checked_at=checked_at, checks=checks)
