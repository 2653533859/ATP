"""HTTP performance testing API thin slice."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_project_access
from app.core.config import settings
from app.core.database import get_db
from app.core import minio_client
from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.performance import (
    PerformanceRunOut,
    PerformanceRunTrigger,
    PerformanceRunRawResultOut,
    PerformanceScriptUploadOut,
    PerformanceTestCreate,
    PerformanceTestOut,
    PerformanceTestUpdate,
)
from app.worker.tasks_performance import run_performance_test

router = APIRouter(tags=["性能压测"])

_MAX_K6_SCRIPT_SIZE = 2 * 1024 * 1024
_ALLOWED_K6_SCRIPT_SUFFIXES = {".js", ".mjs"}
_TARGET_ENV_KEYS = {"TARGET_URL", "BASE_URL", "URL"}
_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*$", re.IGNORECASE)


def _safe_script_filename(filename: str | None) -> str:
    name = Path(filename or "script.js").name
    stem = Path(name).stem or "script"
    suffix = Path(name).suffix.lower() or ".js"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip(".-") or "script"
    return f"{safe_stem}{suffix}"


def _performance_script_object_name(project_id: int, filename: str) -> str:
    return f"performance/scripts/{project_id}/{uuid4().hex}-{_safe_script_filename(filename)}"


def _merge_options(default_options: dict | None, override: dict | None) -> dict:
    merged = dict(default_options or {})
    merged.update(override or {})
    env = dict((default_options or {}).get("env") or {})
    env.update((override or {}).get("env") or {})
    if env:
        merged["env"] = env
    return merged


def _parse_duration_seconds(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
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


def _max_vus_from_options(options: dict) -> int:
    candidates: list[int] = []
    try:
        if options.get("vus") is not None:
            candidates.append(int(options["vus"]))
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
    return max(candidates or [0.0])


def _target_hosts_from_options(options: dict) -> set[str]:
    hosts: set[str] = set()
    env = options.get("env") if isinstance(options.get("env"), dict) else {}
    for key, value in env.items():
        if str(key).upper() not in _TARGET_ENV_KEYS or not isinstance(value, str):
            continue
        parsed = urlparse(value)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return hosts


def _allowed_performance_hosts() -> set[str]:
    return {
        item.strip().lower()
        for item in settings.PERFORMANCE_TARGET_ALLOWLIST.split(",")
        if item.strip()
    }


def _host_allowed(host: str, allowed: set[str]) -> bool:
    return not allowed or host in allowed or any(host.endswith(f".{item}") for item in allowed)


def _validate_performance_options(options: dict) -> None:
    if not isinstance(options, dict):
        raise HTTPException(status_code=400, detail="压测 options 必须是 JSON 对象")
    max_vus = _max_vus_from_options(options)
    if max_vus > settings.PERFORMANCE_MAX_VUS:
        raise HTTPException(
            status_code=400,
            detail=f"压测 VUs 超过上限 {settings.PERFORMANCE_MAX_VUS}",
        )
    max_duration = _max_duration_from_options(options)
    if max_duration > settings.PERFORMANCE_MAX_DURATION_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"压测 duration 超过上限 {settings.PERFORMANCE_MAX_DURATION_SECONDS}s",
        )
    allowed = _allowed_performance_hosts()
    blocked = sorted(host for host in _target_hosts_from_options(options) if not _host_allowed(host, allowed))
    if blocked:
        raise HTTPException(status_code=400, detail=f"压测目标域名不在 allowlist: {', '.join(blocked)}")


@router.get("/projects/{project_id}/performance/tests", response_model=list[PerformanceTestOut])
async def list_performance_tests(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_project_access(ProjectRole.viewer)),
):
    result = await db.execute(
        select(PerformanceTest)
        .where(PerformanceTest.project_id == project_id)
        .order_by(PerformanceTest.id.desc())
    )
    return result.scalars().all()


@router.post("/performance/tests", response_model=PerformanceTestOut, status_code=status.HTTP_201_CREATED)
async def create_performance_test(
    body: PerformanceTestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    _validate_performance_options(body.default_options)
    item = PerformanceTest(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        executor=body.executor,
        script_object_name=body.script_object_name,
        default_options=body.default_options,
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
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    filename = _safe_script_filename(file.filename)
    if Path(filename).suffix.lower() not in _ALLOWED_K6_SCRIPT_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持上传 .js 或 .mjs k6 脚本")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="脚本文件不能为空")
    if len(content) > _MAX_K6_SCRIPT_SIZE:
        raise HTTPException(status_code=413, detail="脚本文件超过 2MB 限制")

    object_name = _performance_script_object_name(project_id, filename)
    minio_client.ensure_bucket()
    minio_client.upload_bytes(object_name, content, content_type="application/javascript")
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
    if body.name is not None:
        item.name = body.name
    if body.description is not None:
        item.description = body.description
    if body.script_object_name is not None:
        item.script_object_name = body.script_object_name
    if body.default_options is not None:
        _validate_performance_options(body.default_options)
        item.default_options = body.default_options
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
    options_snapshot = _merge_options(item.default_options, body.options)
    _validate_performance_options(options_snapshot)

    run = PerformanceRun(
        performance_test_id=item.id,
        project_id=item.project_id,
        environment_id=body.environment_id,
        status=PerformanceRunStatus.pending.value,
        triggered_by=user.id,
        options_snapshot=options_snapshot,
        summary={},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_performance_test.delay(run.id)
    return run


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
