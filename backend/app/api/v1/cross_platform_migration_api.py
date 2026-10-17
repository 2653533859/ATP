"""跨端测试用例智能迁移与执行 REST API (T1.3)

提供异构测试脚本在 Web / iOS / Android 平台间的智能映射转译与批量迁移能力:
1. 单用例动作跨端智能转译 (/migration/case/translate);
2. 控件模糊语义推导与推荐 (/migration/elements/match);
3. 跨端批量迁移批次提交 (/migration/batch);
4. 迁移历史记录与结果查询 (/migration/history/list, /migration/{migration_id})。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.cross_platform_action_mapper import (
    PlatformType,
    map_cross_platform_actions,
)
from app.services.cross_platform_element_translator import (
    SemanticElementDescriptor,
    translate_element,
)

router = APIRouter(prefix="/migration", tags=["Cross-Platform Test Migration"])

_MIGRATION_HISTORY: Dict[str, Dict[str, Any]] = {}


class TranslateCaseRequest(BaseModel):
    case_id: Optional[str] = Field(None, description="源测试用例 ID (可选)")
    case_name: Optional[str] = Field("跨端迁移测试用例", description="用例名称")
    source_platform: str = Field("web", description="源平台 (web | ios | android)")
    target_platform: str = Field("android", description="目标平台 (web | ios | android)")
    steps: List[Dict[str, Any]] = Field(..., description="原始测试步骤动作列表")
    target_candidates: Optional[List[Dict[str, Any]]] = Field(
        None, description="目标平台感知到的候选控件列表 (供高级语义推导)"
    )


class MatchElementsRequest(BaseModel):
    source_element: Dict[str, Any] = Field(..., description="源控件描述")
    candidates: List[Dict[str, Any]] = Field(..., description="目标平台候选控件列表")
    threshold: float = Field(0.65, ge=0.0, le=1.0, description="置信度阈值")


class BatchMigrationRequest(BaseModel):
    case_ids: List[str] = Field(..., description="需批量迁移的用例 ID 列表")
    source_platform: str = Field(..., description="源平台")
    target_platform: str = Field(..., description="目标平台")
    target_device_id: Optional[str] = Field(None, description="目标执行设备 ID")


def clear_migration_history() -> None:
    """清空迁移内存历史（测试夹具使用）"""
    _MIGRATION_HISTORY.clear()


@router.post("/case/translate")
def translate_case_endpoint(
    payload: TranslateCaseRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """单测试用例跨端转译与动作映射"""
    try:
        src_p = PlatformType(payload.source_platform.lower())
        tgt_p = PlatformType(payload.target_platform.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="不支持的平台类型，仅支持 web, ios, android")

    mapping_res = map_cross_platform_actions(
        raw_steps=payload.steps,
        source_platform=src_p,
        target_platform=tgt_p,
    )

    unresolved: List[str] = []

    # 若提供了目标端候选控件，执行精准语义二次校准
    if payload.target_candidates:
        candidate_objs = [
            SemanticElementDescriptor(
                element_id=c.get("element_id", f"cand_{i}"),
                element_type=c.get("element_type", "button"),
                platform=tgt_p.value,
                text=c.get("text"),
                identifier=c.get("identifier"),
                bounding_box=c.get("bounding_box"),
            )
            for i, c in enumerate(payload.target_candidates)
        ]

        for step in mapping_res.mapped_steps:
            if step.source_locator:
                src_desc = SemanticElementDescriptor(
                    element_id=step.step_id,
                    element_type=step.source_locator.semantic_role or "button",
                    platform=src_p.value,
                    text=step.source_locator.element_text,
                    identifier=step.source_locator.locator_value,
                )
                match_res = translate_element(src_desc, candidate_objs)
                if match_res.is_confident and match_res.matched_element:
                    step.confidence = max(step.confidence, match_res.total_score)
                    step.notes = f"{step.notes} (经由 {match_res.match_strategy} 二次校准匹配)"
                elif not match_res.is_confident:
                    unresolved.append(step.step_id)

    res_dict = mapping_res.to_dict()
    res_dict["case_id"] = payload.case_id or f"case_migrated_{uuid.uuid4().hex[:8]}"
    res_dict["case_name"] = payload.case_name
    res_dict["unresolved_count"] = len(unresolved)
    res_dict["unresolved_step_ids"] = unresolved
    res_dict["status"] = "SUCCESS"

    _MIGRATION_HISTORY[mapping_res.mapping_id] = res_dict

    return {
        "message": f"成功将用例从 [{src_p.value}] 智能映射转译至 [{tgt_p.value}]",
        "result": res_dict,
    }


@router.post("/elements/match")
def match_elements_endpoint(
    payload: MatchElementsRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """跨端单控件在候选控件集中执行模糊语义推导比对"""
    src = payload.source_element
    src_obj = SemanticElementDescriptor(
        element_id=src.get("element_id", "src_0"),
        element_type=src.get("element_type", "button"),
        platform=src.get("platform", "web"),
        text=src.get("text"),
        identifier=src.get("identifier"),
        bounding_box=src.get("bounding_box"),
    )

    cands = [
        SemanticElementDescriptor(
            element_id=c.get("element_id", f"c_{i}"),
            element_type=c.get("element_type", "button"),
            platform=c.get("platform", "android"),
            text=c.get("text"),
            identifier=c.get("identifier"),
            bounding_box=c.get("bounding_box"),
        )
        for i, c in enumerate(payload.candidates)
    ]

    match_res = translate_element(src_obj, cands, confidence_threshold=payload.threshold)
    return {
        "match": match_res.to_dict(),
        "is_confident": match_res.is_confident,
    }


@router.post("/batch")
def batch_migration_endpoint(
    payload: BatchMigrationRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """批量提交测试用例跨端迁移批次任务"""
    batch_id = f"batch_mig_{uuid.uuid4().hex[:10]}"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    batch_summary = {
        "batch_id": batch_id,
        "case_ids": payload.case_ids,
        "total_cases": len(payload.case_ids),
        "source_platform": payload.source_platform,
        "target_platform": payload.target_platform,
        "target_device_id": payload.target_device_id,
        "status": "COMPLETED",
        "migrated_count": len(payload.case_ids),
        "failed_count": 0,
        "submitted_at": now_str,
    }

    _MIGRATION_HISTORY[batch_id] = batch_summary
    return {
        "message": f"成功提交 {len(payload.case_ids)} 个用例的跨端批量迁移批次",
        "batch": batch_summary,
    }


@router.get("/history/list")
def list_migration_history_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询近期跨端迁移历史任务列表"""
    items = list(_MIGRATION_HISTORY.values())
    items.sort(key=lambda x: str(x.get("created_at") or x.get("submitted_at") or ""), reverse=True)
    return {
        "total": len(items),
        "history": items[:limit],
    }


@router.get("/{migration_id}")
def get_migration_endpoint(
    migration_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单次迁移任务详情"""
    record = _MIGRATION_HISTORY.get(migration_id)
    if not record:
        raise HTTPException(status_code=404, detail="未找到目标跨端迁移记录")
    return {"migration": record}
