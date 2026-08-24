"""HTTP performance testing API thin slice."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps import assert_project_access, get_current_user, require_engineer, require_project_access
from app.core.config import settings
from app.core.database import get_db
from app.core import minio_client
from app.core.encryption import decrypt_env_vars, encrypt
from app.models.environment import Environment, EnvVariable
from app.models.performance import PerformanceMetricSample, PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.models.performance_node import PerformanceNode
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.performance import (
    PerformanceBaselineComparisonOut,
    PerformanceBaselineUpdate,
    PerformanceCapacityAnalyzeRequest,
    PerformanceGateOut,
    PerformanceRunOut,
    PerformanceMetricSampleOut,
    PerformanceTrendOut,
    PerformanceRunTrigger,
    PerformanceRunRawResultOut,
    PerformanceScriptUploadOut,
    PerformanceScheduleUpdate,
    PerformanceTestCreate,
    PerformanceTestOut,
    PerformanceTestUpdate,
    PerformanceExecutor,
    PerformanceExecutorOut,
)
from app.schemas.performance_node import PerformanceNodeCreate, PerformanceNodeOut, PerformanceNodeUpdate
from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY
from app.services.performance_control import request_cancel
from app.services.performance_report import (
    apply_baseline_gate,
    build_baseline_comparison,
    build_performance_gate,
    build_threshold_gate,
    build_threshold_rows,
)
from app.services.performance_schedule import next_schedule_time
from app.services.performance_node import (
    PerformanceNodeConstraintError,
    effective_node_status,
    enqueue_performance_run,
    node_has_capacity,
    parse_egress_allowlist,
    validate_node_options,
)
from app.services.performance_idempotency import (
    PerformanceIdempotencyConflict,
    build_idempotency_fingerprint,
    find_idempotent_run,
    normalize_idempotency_key,
)
from app.services.performance_dataset import PerformanceDatasetBindingError, resolve_dataset_binding
from app.services.performance_dataset import load_dataset_rows, serialize_dataset_rows
from app.services.performance_grpc import GrpcPerformanceOptionsError, target_hostname, validate_grpc_options
from app.services.performance_executor import (
    PerformanceExecutorError,
    ensure_ready_executor,
    list_executor_capabilities,
    node_supports_executor,
)
from app.services.performance_sharding import PerformanceShardingError, split_performance_options
from app.services.performance_capacity import analyze_capacity_runs
from app.services.performance_trend import build_performance_trend
from app.services.performance_ramp import PerformanceRampError, expand_auto_ramp
from app.services.performance_metric_boundary import PerformanceMetricBoundaryError, build_metric_boundary
from app.worker.tasks_performance import run_performance_test

router = APIRouter(tags=["性能压测"])

_MAX_PERFORMANCE_SCRIPT_SIZE = 2 * 1024 * 1024
_TARGET_ENV_KEYS = {"TARGET_URL", "BASE_URL", "URL"}
_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*$", re.IGNORECASE)
_SENSITIVE_ENV_KEY_RE = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|credential|authorization|cookie)", re.IGNORECASE
)


@router.get("/performance/executors", response_model=list[PerformanceExecutorOut])
async def list_performance_executors(
    _: User = Depends(get_current_user),
):
    """Expose the executor capability matrix to the authoring UI."""
    return [PerformanceExecutorOut(**item.public_dict()) for item in list_executor_capabilities()]


def _safe_script_filename(filename: str | None) -> str:
    name = Path(filename or "script.js").name
    stem = Path(name).stem or "script"
    suffix = Path(name).suffix.lower() or ".js"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip(".-") or "script"
    return f"{safe_stem}{suffix}"


def _performance_script_object_name(project_id: int, filename: str) -> str:
    return f"performance/scripts/{project_id}/{uuid4().hex}-{_safe_script_filename(filename)}"


def _validate_script_suffix(executor: str, script_object_name: str) -> None:
    try:
        capability = ensure_ready_executor(executor)
    except PerformanceExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if Path(script_object_name).suffix.lower() not in capability.script_extensions:
        extensions = ", ".join(capability.script_extensions)
        raise HTTPException(status_code=400, detail=f"{capability.label} 执行器仅支持脚本类型: {extensions}")


def _merge_options(default_options: dict | None, override: dict | None) -> dict:
    merged = dict(default_options or {})
    merged.update(override or {})
    env = dict((default_options or {}).get("env") or {})
    env.update((override or {}).get("env") or {})
    if env:
        merged["env"] = env
    return merged


def _validate_environment_overrides(options: dict | None) -> None:
    env = (options or {}).get("env") if isinstance(options, dict) else None
    if not isinstance(env, dict):
        return
    for key, value in env.items():
        if _SENSITIVE_ENV_KEY_RE.search(str(key)) and str(value).strip():
            raise HTTPException(
                status_code=400,
                detail=f"敏感变量 {key} 必须通过所选环境注入，不能直接写入压测参数",
            )


async def _load_environment_variables(db: AsyncSession, environment_id: int, project_id: int) -> tuple[dict, set[str]]:
    """Load environment variables for validation without exposing secret values in the run snapshot."""
    environment = await db.get(Environment, environment_id)
    if environment is None:
        raise HTTPException(status_code=404, detail="目标环境不存在")
    if environment.project_id != project_id:
        raise HTTPException(status_code=400, detail="目标环境不属于当前项目")

    result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == environment_id))
    variables = result.scalars().all()
    return decrypt_env_vars(variables), {variable.key for variable in variables if variable.is_secret}


def _build_options_snapshot(
    default_options: dict | None,
    override: dict | None,
    environment_values: dict,
    secret_keys: set[str],
) -> tuple[dict, dict]:
    """Return a safe persisted snapshot and the full runtime options used for validation."""
    try:
        snapshot = expand_auto_ramp(_merge_options(default_options, override))
    except PerformanceRampError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshot_env = dict(snapshot.get("env") or {})

    # Environment variables are loaded again by the worker. Do not duplicate them in the
    # visible run snapshot; secret keys must never be returned through the run API.
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


def _parse_duration_seconds(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) and parsed >= 0 else None
    if not isinstance(value, str):
        return None
    match = _DURATION_RE.match(value)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    if unit == "ms":
        return amount / 1000
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 3600
    return amount


def _validate_duration_fields(options: dict) -> None:
    for key in ("duration", "run_time", "duration_seconds"):
        if key in options and options[key] is not None and _parse_duration_seconds(options[key]) is None:
            raise HTTPException(status_code=400, detail=f"压测 {key} 必须是非负有限时长")

    stages = options.get("stages")
    if not isinstance(stages, list):
        return
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict) or stage.get("duration") is None:
            continue
        if _parse_duration_seconds(stage["duration"]) is None:
            raise HTTPException(status_code=400, detail=f"压测 stages[{index}].duration 必须是非负有限时长")


def _max_vus_from_options(options: dict) -> int:
    candidates: list[int] = []
    try:
        if options.get("vus") is not None:
            candidates.append(int(options["vus"]))
    except (TypeError, ValueError):
        pass
    try:
        if options.get("users") is not None:
            candidates.append(int(options["users"]))
    except (TypeError, ValueError):
        pass
    try:
        if options.get("concurrency") is not None:
            candidates.append(int(options["concurrency"]))
    except (TypeError, ValueError):
        pass
    for stage in options.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        try:
            candidates.append(int(stage.get("target")))
        except (TypeError, ValueError):
            continue
    return max(candidates or [0])


def _max_duration_from_options(options: dict) -> float:
    candidates: list[float] = []
    duration = _parse_duration_seconds(options.get("duration"))
    if duration is not None:
        candidates.append(duration)
    for stage in options.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        stage_duration = _parse_duration_seconds(stage.get("duration"))
        if stage_duration is not None:
            candidates.append(stage_duration)
    if options.get("stages"):
        return sum(candidates)
    run_time = _parse_duration_seconds(options.get("run_time"))
    if run_time is not None:
        candidates.append(run_time)
    duration_seconds = options.get("duration_seconds")
    if isinstance(duration_seconds, (int, float)):
        candidates.append(float(duration_seconds))
    return max(candidates or [0.0])


def _target_hosts_from_options(options: dict) -> set[str]:
    hosts: set[str] = set()
    grpc_host = target_hostname(options.get("target"))
    if grpc_host:
        hosts.add(grpc_host)
    direct_host = options.get("host")
    if isinstance(direct_host, str):
        parsed = urlparse(direct_host)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    env = options.get("env") if isinstance(options.get("env"), dict) else {}
    for key, value in env.items():
        if str(key).upper() not in _TARGET_ENV_KEYS or not isinstance(value, str):
            continue
        parsed = urlparse(value)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    target_metrics = options.get("target_metrics")
    if isinstance(target_metrics, dict):
        target_url = target_metrics.get("prometheus_url") or target_metrics.get("url")
        target_env_key = target_metrics.get("url_env")
        if not target_url and isinstance(target_env_key, str):
            target_url = env.get(target_env_key) or os.getenv(target_env_key)
        if isinstance(target_url, str):
            parsed = urlparse(target_url)
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())
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
                    if str(key).upper() not in _TARGET_ENV_KEYS or not isinstance(value, str):
                        continue
                    parsed = urlparse(value)
                    if parsed.hostname:
                        hosts.add(parsed.hostname.lower())
    return hosts


def _allowed_performance_hosts() -> set[str]:
    return {item.strip().lower() for item in settings.PERFORMANCE_TARGET_ALLOWLIST.split(",") if item.strip()}


def _host_allowed(host: str, allowed: set[str]) -> bool:
    return not allowed or host in allowed or any(host.endswith(f".{item}") for item in allowed)


def _validate_performance_options(options: dict, executor: str = "k6") -> None:
    try:
        ensure_ready_executor(executor)
    except PerformanceExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not isinstance(options, dict):
        raise HTTPException(status_code=400, detail="压测 options 必须是 JSON 对象")
    try:
        normalized_options = expand_auto_ramp(options)
    except PerformanceRampError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _validate_duration_fields(normalized_options)
    try:
        build_metric_boundary(normalized_options)
    except PerformanceMetricBoundaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if executor == "grpc":
        try:
            normalized_options = validate_grpc_options(normalized_options)
        except GrpcPerformanceOptionsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    max_vus = _max_vus_from_options(normalized_options)
    if max_vus > settings.PERFORMANCE_MAX_VUS:
        raise HTTPException(
            status_code=400,
            detail=f"压测 VUs 超过上限 {settings.PERFORMANCE_MAX_VUS}",
        )
    max_duration = _max_duration_from_options(normalized_options)
    if max_duration > settings.PERFORMANCE_MAX_DURATION_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"压测 duration 超过上限 {settings.PERFORMANCE_MAX_DURATION_SECONDS}s",
        )
    allowed = _allowed_performance_hosts()
    blocked = sorted(
        host for host in _target_hosts_from_options(normalized_options) if not _host_allowed(host, allowed)
    )
    if blocked:
        raise HTTPException(status_code=400, detail=f"压测目标域名不在 allowlist: {', '.join(blocked)}")


def _next_schedule_time(cron_expression: str, timezone_name: str, base: datetime | None = None) -> datetime:
    try:
        return next_schedule_time(cron_expression, timezone_name, base)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Cron 表达式或时区无效") from exc


async def _resolve_performance_node(
    db: AsyncSession,
    node_id: int | None,
    runtime_options: dict,
    executor: str = "k6",
) -> PerformanceNode | None:
    if node_id is None:
        return None
    # Keep the node row locked until the caller commits the newly created run.
    # Without this, concurrent API replicas can all observe the same free slot
    # and oversubscribe max_concurrency before any of their runs is committed.
    node = await db.get(PerformanceNode, node_id, with_for_update=True)
    if node is None:
        raise HTTPException(status_code=404, detail="性能压测节点不存在")
    if effective_node_status(node) != "online":
        raise HTTPException(status_code=409, detail="性能压测节点当前不在线或未启用")
    if not node_supports_executor(node, executor):
        raise HTTPException(status_code=409, detail=f"性能压测节点不支持 {executor} 执行器")
    try:
        validate_node_options(runtime_options, node, executor=executor)
    except PerformanceNodeConstraintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not await node_has_capacity(db, node):
        raise HTTPException(status_code=409, detail="性能压测节点并发容量已满")
    return node


async def _resolve_performance_dataset(
    db: AsyncSession,
    dataset_id: int | None,
    project_id: int,
) -> tuple[int, int | None] | None:
    try:
        return await resolve_dataset_binding(db, dataset_id, project_id)
    except PerformanceDatasetBindingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _add_dataset_runtime_options(
    db: AsyncSession,
    options: dict,
    dataset_binding: tuple[int, int | None] | None,
) -> dict:
    if dataset_binding is None:
        return options
    rows = await load_dataset_rows(db, dataset_binding[0], dataset_binding[1])
    enriched = dict(options)
    env = dict(options.get("env") or {})
    env["ATP_DATASET_JSON"] = serialize_dataset_rows(rows)
    enriched["env"] = env
    return enriched


@router.get("/performance/nodes", response_model=list[PerformanceNodeOut])
async def list_performance_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PerformanceNode).order_by(PerformanceNode.status.asc(), PerformanceNode.name.asc())
    )
    nodes = result.scalars().all()
    for node in nodes:
        node.status = effective_node_status(node)
    return nodes


@router.post("/performance/nodes", response_model=PerformanceNodeOut, status_code=status.HTTP_201_CREATED)
async def create_performance_node(
    body: PerformanceNodeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    labels = {**body.labels, "managed_by": "ui"}
    item = PerformanceNode(
        node_id=body.node_id,
        name=body.name,
        queue_name=body.queue_name,
        enabled=body.enabled,
        labels=labels,
        capabilities=body.capabilities,
        max_vus=body.max_vus,
        max_concurrency=body.max_concurrency,
        egress_allowlist=parse_egress_allowlist(body.egress_allowlist),
        status="offline" if body.enabled else "disabled",
    )
    db.add(item)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="性能压测节点 ID 已存在") from exc
    await db.refresh(item)
    return item


@router.get("/performance/nodes/{node_id}", response_model=PerformanceNodeOut)
async def get_performance_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = await db.get(PerformanceNode, node_id)
    if item is None:
        raise HTTPException(status_code=404, detail="性能压测节点不存在")
    item.status = effective_node_status(item)
    return item


@router.patch("/performance/nodes/{node_id}", response_model=PerformanceNodeOut)
async def update_performance_node(
    node_id: int,
    body: PerformanceNodeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    item = await db.get(PerformanceNode, node_id)
    if item is None:
        raise HTTPException(status_code=404, detail="性能压测节点不存在")
    values = body.model_dump(exclude_unset=True)
    values["labels"] = {**(item.labels or {}), "managed_by": "ui"}
    if "egress_allowlist" in values:
        values["egress_allowlist"] = parse_egress_allowlist(values["egress_allowlist"])
    for key, value in values.items():
        setattr(item, key, value)
    if "enabled" in values and not values["enabled"]:
        item.status = "disabled"
    elif values.get("status") == "draining":
        item.status = "draining"
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/performance/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    # Serialize deletion with manual, webhook, and scheduled dispatch. Those
    # paths lock the same node row before checking capacity and inserting a
    # run; without this lock, a run can be inserted after the checks below and
    # lose its node binding through the FK's ON DELETE SET NULL action.
    item = await db.get(PerformanceNode, node_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="性能压测节点不存在")

    active_run = await db.execute(
        select(PerformanceRun.id)
        .where(
            PerformanceRun.performance_node_id == node_id,
            PerformanceRun.status.in_(
                [
                    PerformanceRunStatus.pending.value,
                    PerformanceRunStatus.running.value,
                    PerformanceRunStatus.cancelling.value,
                ]
            ),
        )
        .limit(1)
    )
    if active_run.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="性能压测节点仍有未结束的运行，请先停止或等待运行完成后再删除")

    scheduled_test = await db.execute(
        select(PerformanceTest.id)
        .where(
            PerformanceTest.schedule_node_id == node_id,
            PerformanceTest.schedule_enabled.is_(True),
        )
        .limit(1)
    )
    if scheduled_test.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="性能压测节点仍被启用的定时任务使用，请先解除节点绑定或停用定时任务"
        )

    await db.delete(item)
    await db.commit()


@router.get("/projects/{project_id}/performance/tests", response_model=list[PerformanceTestOut])
async def list_performance_tests(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_project_access(ProjectRole.viewer)),
):
    result = await db.execute(
        select(PerformanceTest).where(PerformanceTest.project_id == project_id).order_by(PerformanceTest.id.desc())
    )
    return result.scalars().all()


@router.post("/performance/tests", response_model=PerformanceTestOut, status_code=status.HTTP_201_CREATED)
async def create_performance_test(
    body: PerformanceTestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    _validate_script_suffix(body.executor, body.script_object_name)
    _validate_environment_overrides(body.default_options)
    _validate_performance_options(body.default_options, body.executor)
    dataset_binding = await _resolve_performance_dataset(db, body.dataset_id, body.project_id)
    item = PerformanceTest(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        executor=body.executor,
        script_object_name=body.script_object_name,
        default_options=body.default_options,
        dataset_id=dataset_binding[0] if dataset_binding else None,
        creator_id=user.id,
    )
    db.add(item)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="压测名称已被项目内占用")
    await db.refresh(item)
    return item


@router.post(
    "/projects/{project_id}/performance/scripts",
    response_model=PerformanceScriptUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_performance_script(
    project_id: int,
    file: UploadFile = File(...),
    executor: PerformanceExecutor = "k6",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    try:
        capability = ensure_ready_executor(executor)
    except PerformanceExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = _safe_script_filename(file.filename)
    if Path(filename).suffix.lower() not in capability.script_extensions:
        extensions = ", ".join(capability.script_extensions)
        raise HTTPException(status_code=400, detail=f"{capability.label} 执行器仅支持上传 {extensions} 脚本")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="脚本文件不能为空")
    if len(content) > _MAX_PERFORMANCE_SCRIPT_SIZE:
        raise HTTPException(status_code=413, detail="脚本文件超过 2MB 限制")

    object_name = _performance_script_object_name(project_id, filename)
    minio_client.ensure_bucket()
    content_type = {
        "k6": "application/javascript",
        "locust": "text/x-python",
        "grpc": "text/plain",
        "jmeter": "application/xml",
    }[capability.name]
    minio_client.upload_bytes(object_name, content, content_type=content_type)
    return PerformanceScriptUploadOut(script_object_name=object_name, filename=filename, size=len(content))


@router.get("/performance/tests/{test_id}", response_model=PerformanceTestOut)
async def get_performance_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(PerformanceTest, test_id)
    if item is None:
        raise HTTPException(status_code=404, detail="压测定义不存在")
    await assert_project_access(db, user, item.project_id, ProjectRole.viewer)
    return item


@router.patch("/performance/tests/{test_id}", response_model=PerformanceTestOut)
async def update_performance_test(
    test_id: int,
    body: PerformanceTestUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(PerformanceTest, test_id)
    if item is None:
        raise HTTPException(status_code=404, detail="压测定义不存在")
    await assert_project_access(db, user, item.project_id, ProjectRole.editor)
    target_executor = body.executor or item.executor
    try:
        ensure_ready_executor(target_executor)
    except PerformanceExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.name is not None:
        item.name = body.name
    if body.description is not None:
        item.description = body.description
    if body.script_object_name is not None:
        _validate_script_suffix(target_executor, body.script_object_name)
        item.script_object_name = body.script_object_name
    elif body.executor is not None and body.executor != item.executor:
        _validate_script_suffix(target_executor, item.script_object_name)
    if body.executor is not None:
        item.executor = body.executor
    if body.default_options is not None:
        _validate_environment_overrides(body.default_options)
        _validate_performance_options(body.default_options, target_executor)
        item.default_options = body.default_options
    if "dataset_id" in body.model_fields_set:
        dataset_binding = await _resolve_performance_dataset(db, body.dataset_id, item.project_id)
        item.dataset_id = dataset_binding[0] if dataset_binding else None
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/performance/tests/{test_id}/baseline", response_model=PerformanceTestOut)
async def set_performance_baseline(
    test_id: int,
    body: PerformanceBaselineUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(PerformanceTest, test_id)
    if item is None:
        raise HTTPException(status_code=404, detail="压测定义不存在")
    await assert_project_access(db, user, item.project_id, ProjectRole.editor)
    baseline = await db.get(PerformanceRun, body.run_id)
    if baseline is None or baseline.performance_test_id != item.id or baseline.project_id != item.project_id:
        raise HTTPException(status_code=400, detail="基线运行不属于当前压测定义")
    if baseline.status != PerformanceRunStatus.success.value:
        raise HTTPException(status_code=400, detail="只有成功完成的运行才能设为基线")
    item.baseline_run_id = baseline.id
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/performance/tests/{test_id}/baseline", response_model=PerformanceTestOut)
async def clear_performance_baseline(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(PerformanceTest, test_id)
    if item is None:
        raise HTTPException(status_code=404, detail="压测定义不存在")
    await assert_project_access(db, user, item.project_id, ProjectRole.editor)
    item.baseline_run_id = None
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/performance/tests/{test_id}/schedule", response_model=PerformanceTestOut)
async def update_performance_schedule(
    test_id: int,
    body: PerformanceScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(PerformanceTest, test_id)
    if item is None:
        raise HTTPException(status_code=404, detail="压测定义不存在")
    await assert_project_access(db, user, item.project_id, ProjectRole.editor)
    if body.enabled and not body.cron_expression:
        raise HTTPException(status_code=400, detail="启用定时执行时必须填写 Cron 表达式")
    schedule_options = body.options or {}
    _validate_environment_overrides(schedule_options)
    environment_values: dict = {}
    secret_keys: set[str] = set()
    if body.environment_id is not None:
        environment_values, secret_keys = await _load_environment_variables(db, body.environment_id, item.project_id)
    _, runtime_options = _build_options_snapshot(
        item.default_options,
        schedule_options,
        environment_values,
        secret_keys,
    )
    dataset_binding = await _resolve_performance_dataset(db, item.dataset_id, item.project_id)
    validation_options = await _add_dataset_runtime_options(db, runtime_options, dataset_binding)
    _validate_performance_options(validation_options, item.executor)
    node = await _resolve_performance_node(db, body.performance_node_id, validation_options, item.executor)

    item.schedule_enabled = body.enabled
    item.cron_expression = body.cron_expression.strip() if body.cron_expression else None
    item.schedule_timezone = body.timezone
    item.schedule_environment_id = body.environment_id
    item.schedule_node_id = node.id if node else None
    item.schedule_options = schedule_options
    if item.schedule_enabled and item.cron_expression:
        item.next_run_at = _next_schedule_time(item.cron_expression, item.schedule_timezone)
    else:
        item.next_run_at = None
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/performance/tests/{test_id}/run", response_model=PerformanceRunOut, status_code=status.HTTP_201_CREATED)
async def trigger_performance_run(
    test_id: int,
    body: PerformanceRunTrigger,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(PerformanceTest, test_id)
    if item is None:
        raise HTTPException(status_code=404, detail="压测定义不存在")
    await assert_project_access(db, user, item.project_id, ProjectRole.editor)
    try:
        idempotency_key = normalize_idempotency_key(body.idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request_fingerprint = build_idempotency_fingerprint(
        source="manual",
        environment_id=body.environment_id,
        performance_node_id=body.performance_node_id,
        performance_node_ids=body.performance_node_ids,
        options=body.options,
    )
    if idempotency_key:
        try:
            existing = await find_idempotent_run(
                db,
                project_id=item.project_id,
                performance_test_id=item.id,
                key=idempotency_key,
                fingerprint=request_fingerprint,
            )
        except PerformanceIdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if existing is not None:
            return existing
    _validate_environment_overrides(item.default_options)
    _validate_environment_overrides(body.options)
    environment_values: dict = {}
    secret_keys: set[str] = set()
    if body.environment_id is not None:
        environment_values, secret_keys = await _load_environment_variables(db, body.environment_id, item.project_id)
    options_snapshot, runtime_options = _build_options_snapshot(
        item.default_options,
        body.options,
        environment_values,
        secret_keys,
    )
    dataset_binding = await _resolve_performance_dataset(db, item.dataset_id, item.project_id)
    validation_options = await _add_dataset_runtime_options(db, runtime_options, dataset_binding)
    _validate_performance_options(validation_options, item.executor)
    if body.performance_node_id is not None and body.performance_node_ids:
        raise HTTPException(status_code=400, detail="performance_node_id 与 performance_node_ids 不能同时传入")
    selected_nodes: list[PerformanceNode] = []
    if body.performance_node_ids:
        if len(set(body.performance_node_ids)) != len(body.performance_node_ids):
            raise HTTPException(status_code=400, detail="性能压测节点不能重复")
        for node_id in body.performance_node_ids:
            selected_nodes.append(await _resolve_performance_node(db, node_id, validation_options, item.executor))
    else:
        node = await _resolve_performance_node(db, body.performance_node_id, validation_options, item.executor)
        if node is not None:
            selected_nodes.append(node)

    if len(selected_nodes) > 1:
        try:
            shard_snapshots = split_performance_options(options_snapshot, len(selected_nodes))
        except PerformanceShardingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        parent = PerformanceRun(
            performance_test_id=item.id,
            project_id=item.project_id,
            environment_id=body.environment_id,
            performance_node_id=None,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=request_fingerprint if idempotency_key else None,
            dataset_id=dataset_binding[0] if dataset_binding else None,
            dataset_version=dataset_binding[1] if dataset_binding else None,
            status=PerformanceRunStatus.pending.value,
            triggered_by=user.id,
            options_snapshot=options_snapshot,
            summary={"sharded": True, "shard_count": len(selected_nodes), "shard_status": "pending"},
        )
        db.add(parent)
        await db.flush()
        children: list[PerformanceRun] = []
        for node, shard_options in zip(selected_nodes, shard_snapshots, strict=True):
            child = PerformanceRun(
                performance_test_id=item.id,
                project_id=item.project_id,
                environment_id=body.environment_id,
                performance_node_id=node.id,
                parent_run_id=parent.id,
                dataset_id=dataset_binding[0] if dataset_binding else None,
                dataset_version=dataset_binding[1] if dataset_binding else None,
                status=PerformanceRunStatus.pending.value,
                triggered_by=user.id,
                options_snapshot=shard_options,
                summary={"shard_index": shard_options["__shard_index"], "shard_count": len(selected_nodes)},
            )
            db.add(child)
            children.append(child)
        await db.flush()
        parent.summary["shard_ids"] = [child.id for child in children]
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if idempotency_key:
                try:
                    existing = await find_idempotent_run(
                        db,
                        project_id=item.project_id,
                        performance_test_id=item.id,
                        key=idempotency_key,
                        fingerprint=request_fingerprint,
                    )
                except PerformanceIdempotencyConflict as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                if existing is not None:
                    return existing
            raise
        await db.refresh(parent)
        for child, node in zip(children, selected_nodes, strict=True):
            enqueue_performance_run(run_performance_test, child.id, node.queue_name)
        return parent

    node = selected_nodes[0] if selected_nodes else None

    run = PerformanceRun(
        performance_test_id=item.id,
        project_id=item.project_id,
        environment_id=body.environment_id,
        performance_node_id=node.id if node else None,
        idempotency_key=idempotency_key,
        idempotency_fingerprint=request_fingerprint if idempotency_key else None,
        dataset_id=dataset_binding[0] if dataset_binding else None,
        dataset_version=dataset_binding[1] if dataset_binding else None,
        status=PerformanceRunStatus.pending.value,
        triggered_by=user.id,
        options_snapshot=options_snapshot,
        summary={},
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if idempotency_key:
            try:
                existing = await find_idempotent_run(
                    db,
                    project_id=item.project_id,
                    performance_test_id=item.id,
                    key=idempotency_key,
                    fingerprint=request_fingerprint,
                )
            except PerformanceIdempotencyConflict as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if existing is not None:
                return existing
        raise
    await db.refresh(run)
    enqueue_performance_run(run_performance_test, run.id, node.queue_name if node else None)
    return run


@router.post("/projects/{project_id}/performance/capacity/analyze", response_model=dict)
async def analyze_performance_capacity(
    project_id: int,
    body: PerformanceCapacityAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Analyze selected runs as a capacity curve without mutating run data."""

    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(PerformanceRun).where(
            PerformanceRun.project_id == project_id,
            PerformanceRun.id.in_(body.run_ids),
        )
    )
    runs = result.scalars().all()
    found_ids = {run.id for run in runs}
    missing_ids = [run_id for run_id in body.run_ids if run_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"压测执行不存在或不属于当前项目: {missing_ids}")
    return analyze_capacity_runs(
        [
            {
                "id": run.id,
                "status": run.status,
                "options_snapshot": run.options_snapshot,
                "summary": run.summary,
            }
            for run in runs
        ],
        max_error_rate=body.max_error_rate,
        max_p95_ms=body.max_p95_ms,
        min_stable_runs=body.min_stable_runs,
    )


@router.get("/performance/runs", response_model=list[PerformanceRunOut])
async def list_performance_runs(
    project_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(PerformanceRun)
        .where(PerformanceRun.project_id == project_id)
        .order_by(PerformanceRun.id.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.get("/projects/{project_id}/performance/trend", response_model=PerformanceTrendOut)
async def get_performance_trend(
    project_id: int,
    days: int = Query(default=30, ge=1, le=365),
    performance_test_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a bounded daily trend without exposing runs from other projects."""

    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    now = datetime.now(timezone.utc)
    start_at = datetime.combine(
        (now - timedelta(days=days - 1)).date(),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    conditions = [
        PerformanceRun.project_id == project_id,
        or_(
            PerformanceRun.created_at >= start_at,
            PerformanceRun.started_at >= start_at,
            PerformanceRun.finished_at >= start_at,
        ),
    ]
    if performance_test_id is not None:
        conditions.append(PerformanceRun.performance_test_id == performance_test_id)
    result = await db.execute(
        select(PerformanceRun).where(*conditions).order_by(PerformanceRun.created_at.asc(), PerformanceRun.id.asc())
    )
    return build_performance_trend(result.scalars().all(), project_id=project_id, days=days, now=now)


@router.get("/performance/runs/{run_id}", response_model=PerformanceRunOut)
async def get_performance_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)
    return run


@router.get("/performance/runs/{run_id}/metrics", response_model=list[PerformanceMetricSampleOut])
async def list_performance_run_metrics(
    run_id: int,
    limit: int = Query(default=2000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)
    sample_limit = limit if isinstance(limit, int) else 2000
    result = await db.execute(
        select(PerformanceMetricSample)
        .where(PerformanceMetricSample.run_id == run_id)
        .order_by(PerformanceMetricSample.captured_at.asc())
        .limit(sample_limit)
    )
    return result.scalars().all()


@router.post("/performance/runs/{run_id}/stop", response_model=PerformanceRunOut)
async def stop_performance_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id, with_for_update=True)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.editor)
    if run.status not in {PerformanceRunStatus.pending.value, PerformanceRunStatus.running.value}:
        raise HTTPException(status_code=409, detail="当前压测状态不支持停止")

    shard_ids = (run.summary or {}).get("shard_ids") if isinstance(run.summary, dict) else None
    shards = []
    if isinstance(shard_ids, list):
        for shard_id in shard_ids:
            try:
                shard = await db.get(PerformanceRun, int(shard_id), with_for_update=True)
            except (TypeError, ValueError):
                shard = None
            if shard is not None:
                shards.append(shard)

    if shards:
        active_shards = [
            shard
            for shard in shards
            if shard.status in {PerformanceRunStatus.running.value, PerformanceRunStatus.cancelling.value}
        ]
        try:
            for shard in active_shards:
                request_cancel(shard.id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="无法发送停止信号，请稍后重试") from exc

        now = datetime.now(timezone.utc)
        for shard in shards:
            if shard.status == PerformanceRunStatus.pending.value:
                shard.status = PerformanceRunStatus.cancelled.value
                shard.finished_at = now
                shard.error_message = "用户已停止压测"
            elif shard.status in {PerformanceRunStatus.running.value, PerformanceRunStatus.cancelling.value}:
                shard.status = PerformanceRunStatus.cancelling.value
                shard.error_message = "正在停止压测"

        if active_shards:
            run.status = PerformanceRunStatus.cancelling.value
            run.error_message = "正在停止压测"
        else:
            run.status = PerformanceRunStatus.cancelled.value
            run.finished_at = now
            run.error_message = "用户已停止压测"
        await db.commit()
        await db.refresh(run)
        return run

    try:
        request_cancel(run.id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="无法发送停止信号，请稍后重试") from exc

    if run.status == PerformanceRunStatus.pending.value:
        run.status = PerformanceRunStatus.cancelled.value
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = "用户已停止压测"
    else:
        run.status = PerformanceRunStatus.cancelling.value
        run.error_message = "正在停止压测"
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/performance/runs/{run_id}/gate", response_model=PerformanceGateOut)
async def get_performance_run_gate(
    run_id: int,
    require_baseline: bool = False,
    fail_on_baseline_regression: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)
    gate = build_performance_gate(run.status, run.summary)
    if not require_baseline and not fail_on_baseline_regression:
        return gate
    test = await db.get(PerformanceTest, run.performance_test_id)
    baseline_id = getattr(test, "baseline_run_id", None)
    baseline = await db.get(PerformanceRun, baseline_id) if baseline_id else None
    baseline_available = bool(
        test
        and baseline
        and baseline.performance_test_id == test.id
        and baseline.project_id == run.project_id
        and baseline.status == PerformanceRunStatus.success.value
    )
    return apply_baseline_gate(
        gate,
        run_id=run.id,
        baseline_run_id=baseline_id,
        baseline_available=baseline_available,
        baseline_summary=baseline.summary if baseline_available else None,
        current_summary=run.summary,
        require_baseline=require_baseline,
        fail_on_baseline_regression=fail_on_baseline_regression,
    )


@router.get(
    "/performance/runs/{run_id}/baseline-comparison",
    response_model=PerformanceBaselineComparisonOut,
)
async def get_performance_baseline_comparison(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)
    test = await db.get(PerformanceTest, run.performance_test_id)
    if test is None or test.baseline_run_id is None:
        raise HTTPException(status_code=409, detail="当前压测尚未设置基线")
    baseline = await db.get(PerformanceRun, test.baseline_run_id)
    if baseline is None or baseline.performance_test_id != test.id:
        raise HTTPException(status_code=409, detail="当前基线已不存在，请重新设置")
    return build_baseline_comparison(baseline.id, run.id, baseline.summary, run.summary)


@router.get("/performance/runs/{run_id}/export/json")
async def export_performance_run_json(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)

    safe_run = PerformanceRunOut.model_validate(run).model_dump(mode="json")
    report = {
        "report_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "run": safe_run,
        "threshold_gate": build_threshold_gate(run.summary),
        "performance_gate": build_performance_gate(run.status, run.summary),
        "thresholds": build_threshold_rows(run.summary),
    }
    return Response(
        content=json.dumps(report, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=performance-run-{run_id}-report.json"},
    )


@router.get("/performance/runs/{run_id}/export/csv")
async def export_performance_run_csv(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)

    safe_run = PerformanceRunOut.model_validate(run).model_dump(mode="json")
    summary = safe_run.get("summary") if isinstance(safe_run.get("summary"), dict) else {}
    gate = build_threshold_gate(run.summary)
    threshold_rows = build_threshold_rows(run.summary) or [{"metric": "", "rule": "", "ok": ""}]
    fieldnames = [
        "run_id",
        "performance_test_id",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "rps",
        "p95_ms",
        "p99_ms",
        "error_rate",
        "threshold_gate",
        "threshold_metric",
        "threshold_rule",
        "threshold_ok",
        "error_message",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for threshold in threshold_rows:
        writer.writerow(
            {
                "run_id": safe_run["id"],
                "performance_test_id": safe_run["performance_test_id"],
                "status": safe_run["status"],
                "started_at": safe_run.get("started_at"),
                "finished_at": safe_run.get("finished_at"),
                "duration_ms": safe_run.get("duration_ms"),
                "rps": summary.get("rps"),
                "p95_ms": summary.get("p95_ms"),
                "p99_ms": summary.get("p99_ms"),
                "error_rate": summary.get("error_rate"),
                "threshold_gate": gate["status"],
                "threshold_metric": threshold["metric"],
                "threshold_rule": threshold["rule"],
                "threshold_ok": threshold["ok"],
                "error_message": safe_run.get("error_message"),
            }
        )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=performance-run-{run_id}-report.csv"},
    )


@router.get("/performance/runs/{run_id}/raw-result", response_model=PerformanceRunRawResultOut)
async def get_performance_run_raw_result(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    await assert_project_access(db, user, run.project_id, ProjectRole.viewer)
    if not run.raw_result_object_name:
        raise HTTPException(status_code=404, detail="原始结果不存在")
    return PerformanceRunRawResultOut(
        url=minio_client.presigned_url(run.raw_result_object_name, expires_seconds=3600),
        filename=f"performance-run-{run.id}-summary.json",
        object_name=run.raw_result_object_name,
    )
