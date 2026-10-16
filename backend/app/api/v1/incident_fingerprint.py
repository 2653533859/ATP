"""历史缺陷向量指纹特征相似度匹配与知识库 REST API (T3.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.incident_knowledge_fingerprint_matcher import (
    clear_incident_knowledge_base,
    delete_known_incident,
    list_known_incidents,
    match_incident_fingerprint,
    register_known_incident,
)

router = APIRouter(prefix="/diagnosis/fingerprint", tags=["已知缺陷指纹匹配与经验推荐 (T3.2)"])


class MatchFingerprintIn(BaseModel):
    error_message: str = Field(..., description="异常报错摘要信息")
    stack_trace: str = Field(default="", description="完整异常调用堆栈文本")
    service_name: str = Field(default="", description="微服务名称 (如 pay-service)")
    min_similarity: float = Field(default=0.55, ge=0.1, le=1.0, description="最低匹配相似度阈值")
    limit: int = Field(default=5, ge=1, le=20, description="最多返回相似条目数")


class RegisterIncidentIn(BaseModel):
    title: str = Field(..., description="缺陷经验标题 (如 MySQL 行锁并发争用死锁)")
    category: str = Field(default="DATABASE", description="缺陷分类: DATABASE | TIMEOUT | 5XX | UI_LOCATOR | AUTH")
    service_name: str = Field(..., description="微服务名称 (如 order-service)")
    error_pattern: str = Field(..., description="典型特征报错信息 (如 Deadlock found when trying to get lock)")
    root_cause_explanation: str = Field(..., description="根本原因说明")
    verified_resolution: str = Field(..., description="经过验证的有效解决方案与规避措施")
    external_ticket_ref: str = Field(default="", description="外部关联工单号 (如 JIRA-5921)")
    incident_id: str | None = Field(default=None, description="指定知识库条目 ID (选填)")


@router.post("/match")
async def match_fingerprint_endpoint(
    body: MatchFingerprintIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """提取报错指纹向量，在已知缺陷知识库中执行余弦/Jaccard 模糊相似度匹配与经验推荐。"""
    _ = _user
    report = match_incident_fingerprint(
        error_message=body.error_message,
        stack_trace=body.stack_trace,
        service_name=body.service_name,
        min_similarity=body.min_similarity,
        limit=body.limit,
    )
    return report.to_dict()


@router.post("/incidents")
async def register_incident_endpoint(
    body: RegisterIncidentIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """录入或更新一条已知缺陷经验知识库条目 (需工程师权限)。"""
    _ = _user
    item = register_known_incident(
        title=body.title,
        category=body.category,
        service_name=body.service_name,
        error_pattern=body.error_pattern,
        root_cause_explanation=body.root_cause_explanation,
        verified_resolution=body.verified_resolution,
        external_ticket_ref=body.external_ticket_ref,
        incident_id=body.incident_id,
    )
    return {"message": "已知缺陷知识条目已录入", "incident": item.to_dict()}


@router.get("/incidents")
async def list_incidents_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询已知缺陷知识库条目清单。"""
    _ = _user
    incidents = list_known_incidents()
    return {"total": len(incidents), "incidents": [i.to_dict() for i in incidents]}


@router.delete("/incidents/{incident_id}")
async def delete_incident_endpoint(
    incident_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """删除指定已知缺陷知识库条目 (需工程师权限)。"""
    _ = _user
    ok = delete_known_incident(incident_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到该知识库条目: {incident_id}",
        )
    return {"message": "知识库条目已删除", "incident_id": incident_id}


@router.delete("/incidents")
async def clear_incidents_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空已知缺陷知识库 (需工程师权限)。"""
    _ = _user
    c = clear_incident_knowledge_base()
    return {"message": f"已清空 {c} 条知识库记录", "cleared_count": c}
