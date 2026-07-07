"""cases 包 - 通用辅助函数与数据库 helper。

这里只放无 router 装饰器的纯函数与异步 helper。
被 monkeypatch 的函数（如 ``_generate_case_code`` / ``_get_case_detail_or_404``）
通过 ``cases/__init__.py`` 重导出到 ``app.api.v1.cases`` 命名空间，
子模块需要调用时统一通过 ``import app.api.v1.cases as _cases`` 然后 ``_cases.X(...)``，
这样测试中 ``monkeypatch.setattr(cases, "X", fake)`` 仍能生效。
"""

from __future__ import annotations

import copy
import json
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import CaseSnapshot, CaseStatus, CaseStep, CaseType, TestCase
from app.models.project import Module


def _normalize_code_fragment(name: str, fallback_prefix: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", " ", name or "").strip()
    if compact:
        parts = [part[:4].upper() for part in compact.split()[:3]]
        merged = "".join(parts)
        if merged:
            return merged[:12]
    return fallback_prefix


def _type_code(case_type: CaseType) -> str:
    mapping = {
        CaseType.api: "API",
        CaseType.web: "WEB",
        CaseType.android: "AND",
        CaseType.graphql: "GQL",
        CaseType.websocket: "WS",
        CaseType.grpc: "GRPC",
    }
    return mapping[case_type]


def _serialize_steps(steps: list[CaseStep] | list[object]) -> list[dict]:
    ordered = sorted(steps, key=lambda item: getattr(item, "step_no", 0))
    return [
        {
            "step_no": getattr(step, "step_no", index + 1),
            "action": getattr(step, "action", ""),
            "test_data": getattr(step, "test_data", None),
            "expected_result": getattr(step, "expected_result", None),
            "is_key_step": bool(getattr(step, "is_key_step", False)),
            "remarks": getattr(step, "remarks", None),
        }
        for index, step in enumerate(ordered)
    ]


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            if item:
                normalized.append(item)
            continue
        normalized.append(str(item))
    return normalized


def _normalize_case_legacy_fields(case: TestCase) -> TestCase:
    case.preconditions = _normalize_string_list(case.preconditions)
    case.postconditions = _normalize_string_list(case.postconditions)
    case.tags = _normalize_string_list(case.tags)
    return case


def _serialize_case_snapshot(case: TestCase) -> dict:
    return {
        "case_code": case.case_code,
        "name": case.name,
        "description": case.description,
        "summary": case.summary,
        "case_type": case.case_type.value,
        "status": case.status.value,
        "priority": case.priority,
        "case_level": case.case_level,
        "review_status": case.review_status,
        "automation_status": case.automation_status,
        "module_id": case.module_id,
        "creator_id": case.creator_id,
        "owner_id": case.owner_id,
        "preconditions": _normalize_string_list(case.preconditions),
        "postconditions": _normalize_string_list(case.postconditions),
        "tags": _normalize_string_list(case.tags),
        "config": copy.deepcopy(case.config or {}),
        "steps": _serialize_steps(case.steps or []),
    }


def _build_snapshot(case: TestCase, version: int, updated_by: int) -> CaseSnapshot:
    snapshot_data = _serialize_case_snapshot(case)
    return CaseSnapshot(
        case_id=case.id,
        version=version,
        name=case.name,
        description=case.description,
        tags=_normalize_string_list(case.tags),
        config=copy.deepcopy(case.config or {}),
        snapshot_data=snapshot_data,
        updated_by=updated_by,
    )


def _derive_steps_from_config(case_type: CaseType, config: dict, fallback_name: str) -> list[dict]:
    config = config or {}
    raw_steps = config.get("steps")
    if isinstance(raw_steps, list) and raw_steps:
        derived_steps: list[dict] = []
        for index, step in enumerate(raw_steps, start=1):
            params = step.get("params") if isinstance(step, dict) else None
            test_data = params if params is not None else step
            expected = step.get("assertions") if isinstance(step, dict) else None
            if not expected and isinstance(step, dict):
                expected = step.get("expected_result") or step.get("text")
            derived_steps.append(
                {
                    "step_no": index,
                    "action": step.get("name") or step.get("action") or f"{fallback_name} step {index}",
                    "test_data": json.dumps(test_data, ensure_ascii=False) if test_data is not None else None,
                    "expected_result": (
                        json.dumps(expected, ensure_ascii=False)
                        if isinstance(expected, (dict, list))
                        else (str(expected) if expected not in (None, "") else None)
                    ),
                    "is_key_step": index == 1,
                    "remarks": None,
                }
            )
        return derived_steps

    if config.get("script_path"):
        return [
            {
                "step_no": 1,
                "action": f"Execute {case_type.value} automation script",
                "test_data": config.get("script_path"),
                "expected_result": "Script completes successfully",
                "is_key_step": True,
                "remarks": None,
            }
        ]

    return [
        {
            "step_no": 1,
            "action": f"Execute {fallback_name}",
            "test_data": None,
            "expected_result": None,
            "is_key_step": True,
            "remarks": None,
        }
    ]


def _normalize_steps(body_steps: list[object], case_type: CaseType, config: dict, fallback_name: str) -> list[dict]:
    source = body_steps or _derive_steps_from_config(case_type, config, fallback_name)
    normalized: list[dict] = []
    for index, step in enumerate(source, start=1):
        if hasattr(step, "model_dump"):
            payload = step.model_dump()
        else:
            payload = dict(step)
        normalized.append(
            {
                "step_no": payload.get("step_no") or index,
                "action": payload.get("action") or f"Step {index}",
                "test_data": payload.get("test_data"),
                "expected_result": payload.get("expected_result"),
                "is_key_step": bool(payload.get("is_key_step", False)),
                "remarks": payload.get("remarks"),
            }
        )
    normalized.sort(key=lambda item: item["step_no"])
    for index, item in enumerate(normalized, start=1):
        item["step_no"] = index
    return normalized


async def _replace_case_steps(db: AsyncSession, case: TestCase, steps_payload: list[dict]) -> None:
    if case.id is not None and case.steps:
        case.steps.clear()
        await db.flush()

    case.steps.extend(
        [
            CaseStep(
                step_no=step["step_no"],
                action=step["action"],
                test_data=step.get("test_data"),
                expected_result=step.get("expected_result"),
                is_key_step=step.get("is_key_step", False),
                remarks=step.get("remarks"),
            )
            for step in steps_payload
        ]
    )


async def _next_snapshot_version(db: AsyncSession, case_id: int) -> int:
    await db.execute(select(TestCase.id).where(TestCase.id == case_id).with_for_update())
    max_ver = await db.scalar(
        select(func.coalesce(func.max(CaseSnapshot.version), 0)).where(CaseSnapshot.case_id == case_id)
    )
    return (max_ver or 0) + 1


async def _enforce_snapshot_retention(db: AsyncSession, case_id: int, max_count: int | None = None) -> int:
    """删除超过保留数的最旧快照，返回被删除的数量。max_count <= 0 表示不限制。"""
    from app.core.config import settings

    cap = max_count if max_count is not None else settings.CASE_SNAPSHOT_MAX_PER_CASE
    if cap <= 0:
        return 0
    if not hasattr(db, "scalar") or not hasattr(db, "execute"):
        return 0
    total = await db.scalar(select(func.count(CaseSnapshot.id)).where(CaseSnapshot.case_id == case_id))
    total = int(total or 0)
    if total <= cap:
        return 0
    excess = total - cap
    old_ids = (
        (
            await db.execute(
                select(CaseSnapshot.id)
                .where(CaseSnapshot.case_id == case_id)
                .order_by(CaseSnapshot.version.asc())
                .limit(excess)
            )
        )
        .scalars()
        .all()
    )
    if not old_ids:
        return 0
    for sid in old_ids:
        snap = await db.get(CaseSnapshot, sid)
        if snap:
            await db.delete(snap)
    await db.flush()
    return len(old_ids)


async def _get_case_detail_or_404(db: AsyncSession, case_id: int) -> TestCase:
    result = await db.execute(select(TestCase).where(TestCase.id == case_id).options(selectinload(TestCase.steps)))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return _normalize_case_legacy_fields(case)


async def _get_module_for_case_code(db: AsyncSession, module_id: int) -> Module:
    result = await db.execute(select(Module).where(Module.id == module_id).options(selectinload(Module.project)))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    project = module.project
    if project is None:
        raise HTTPException(status_code=400, detail="模块缺少所属项目")
    if not project.project_code:
        project.project_code = _normalize_code_fragment(project.name, f"P{project.id}")
    if not module.module_code:
        module.module_code = _normalize_code_fragment(module.name, f"M{module.id}")
    return module


async def _generate_case_code(db: AsyncSession, module: Module, case_type: CaseType) -> str:
    prefix = f"{module.project.project_code}-{module.module_code}-{_type_code(case_type)}"
    result = await db.execute(
        select(TestCase.case_code)
        .where(TestCase.module_id == module.id, TestCase.case_type == case_type)
        .order_by(TestCase.id.desc())
    )
    max_sequence = 0
    for case_code in result.scalars().all():
        if not case_code or not case_code.startswith(prefix):
            continue
        suffix = case_code.rsplit("-", 1)[-1]
        if suffix.isdigit():
            max_sequence = max(max_sequence, int(suffix))
    return f"{prefix}-{max_sequence + 1:04d}"


def _reset_review_after_edit(case: TestCase) -> None:
    case.status = CaseStatus.draft
    case.review_status = "pending"
    case.submitted_at = None
    case.reviewed_at = None
    case.reviewed_by = None
    case.review_comment = None


def _assert_can_trigger_run(case: TestCase) -> None:
    if case.status != CaseStatus.active:
        raise HTTPException(status_code=409, detail="仅 active 状态用例可执行")
    if case.review_status != "approved":
        raise HTTPException(status_code=409, detail="仅审核通过的用例可执行")
    if case.automation_status not in {"auto", "semi_auto"}:
        raise HTTPException(status_code=409, detail="当前用例未配置为可自动执行")
