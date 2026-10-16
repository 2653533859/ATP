"""页面内存泄漏与 DOM 节点脱落幽灵引用诊断 REST API (T4.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.client_memory_leak_dom_detachment_detector import (
    clear_memory_leak_store,
    diagnose_memory_leak_and_detachment,
    get_memory_leak_report,
    list_memory_leak_reports,
)

router = APIRouter(prefix="/client-perf/memory-leak", tags=["内存泄漏与 DOM 幽灵引用 (T4.2)"])


class HeapSnapshotIn(BaseModel):
    timestamp_ms: float | None = Field(default=None, description="快照时间戳 ms")
    js_heap_used_bytes: int = Field(..., description="已使用 JS Heap 字节数")
    js_heap_total_bytes: int | None = Field(default=None, description="分配总堆字节数")
    detached_dom_node_count: int = Field(default=0, description="脱落游离 DOM 节点数量")
    event_listener_count: int = Field(default=0, description="活跃事件监听器数量")


class DetachedDomNodeIn(BaseModel):
    node_id: str = Field(..., description="节点 ID 或标记")
    tag_name: str = Field(default="div", description="HTML 标签名")
    retained_size_bytes: int = Field(default=4096, description="持有保留字节大小")
    retaining_closure: str | None = Field(default=None, description="引用它的闭包或全局变量")
    description: str | None = Field(default=None, description="描述")


class AnalyzeMemoryLeakIn(BaseModel):
    page_or_scenario: str = Field(default="drawer_open_close_test", description="测试场景或页面名")
    snapshots: list[HeapSnapshotIn] = Field(..., min_length=1, description="时序内存与监听器快照")
    detached_nodes: list[DetachedDomNodeIn] = Field(default_factory=list, description="脱落节点详细样本")


@router.post("/analyze")
async def analyze_memory_leak_endpoint(
    body: AnalyzeMemoryLeakIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """分析时序快照，深度评估堆增长趋势、未解绑监听器与脱落 DOM 泄漏。"""
    _ = _user
    snapshots_dicts = [s.model_dump() for s in body.snapshots]
    nodes_dicts = [n.model_dump() for n in body.detached_nodes]
    report = diagnose_memory_leak_and_detachment(
        page_or_scenario=body.page_or_scenario,
        snapshots=snapshots_dicts,
        detached_nodes=nodes_dicts,
    )
    return {"message": "内存泄漏与 DOM 幽灵引用诊断完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史内存审计报告列表。"""
    _ = _user
    reports = list_memory_leak_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次内存诊断报告详情。"""
    _ = _user
    report = get_memory_leak_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空内存泄漏诊断报告仓库 (需工程师权限)。"""
    _ = _user
    clear_memory_leak_store()
    return {"message": "已清空所有内存泄漏诊断报告"}
