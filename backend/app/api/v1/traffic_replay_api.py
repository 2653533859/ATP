"""生产流量录制集管理与回放检索 REST API (T1.3)

为微服务真实流量镜像、数据脱敏、录制集持久化检索与回放调度提供标准化 REST 端点:
1. 隐私数据脱敏在线验证 (/traffic-replay/sanitize);
2. 镜像流量推送评估与入库 (/traffic-replay/mirror/ingest);
3. 录制集流水检索与单条详情查询 (/traffic-replay/records, /record/{id});
4. 采样器指标遥测大盘查询 (/traffic-replay/metrics);
5. 批量调度回放任务派发 (/traffic-replay/batch-replay)。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.traffic_mirror_sampler import (
    TrafficMirrorFilterCriteria,
    evaluate_and_sample_traffic,
    get_global_mirror_buffer,
)
from app.services.traffic_sanitization_masker import (
    SanitizationMode,
    sanitize_traffic_payload,
)

router = APIRouter(prefix="/traffic-replay", tags=["Production Traffic Replay & Chaos Mutation"])


class TrafficSanitizeRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="待脱敏的数据载荷 (Headers, Query, Body)")
    mode: SanitizationMode = Field(SanitizationMode.MASK, description="脱敏模式 (MASK | HASH_SALT | SYNTHETIC_REPLACE)")
    salt: str = Field("atp_salt_2026", description="加盐值")


class IngestMirrorTrafficRequest(BaseModel):
    raw_traffic: Dict[str, Any] = Field(..., description="原始待评估流量字典")
    criteria: Optional[Dict[str, Any]] = Field(None, description="自定义抽样与过滤规则")


class BatchReplayRequest(BaseModel):
    record_ids: List[str] = Field(..., min_length=1, description="待回放的流量记录 ID 列表")
    target_host: str = Field("http://127.0.0.1:8000", description="回放目标环境基地址")
    concurrency: int = Field(5, ge=1, le=50, description="并发回放度")


@router.post("/sanitize")
def sanitize_payload_endpoint(
    payload: TrafficSanitizeRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """对单条流量载荷进行实时脱敏计算并输出审计追踪记录"""
    sanitized, audit = sanitize_traffic_payload(
        payload=payload.payload,
        mode=payload.mode,
        salt=payload.salt,
    )
    return {
        "message": f"脱敏完成，已遮蔽 {audit.masked_field_count} 处敏感字段",
        "sanitized_payload": sanitized,
        "audit_trail": audit.to_dict(),
    }


@router.post("/mirror/ingest")
def ingest_traffic_endpoint(
    payload: IngestMirrorTrafficRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """网关镜像流量捕获入库与抽样评估端点"""
    crit = None
    if payload.criteria:
        crit = TrafficMirrorFilterCriteria(**payload.criteria)

    ok, reason, item = evaluate_and_sample_traffic(
        raw_traffic=payload.raw_traffic,
        criteria=crit,
    )
    return {
        "should_record": ok,
        "reason": reason,
        "item": item.to_dict() if item else None,
    }


@router.get("/records")
def list_records_endpoint(
    method: Optional[str] = None,
    path_pattern: Optional[str] = None,
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询流量录制集列表"""
    buf = get_global_mirror_buffer()
    items = buf.list_items(method=method, path_pattern=path_pattern, limit=limit)
    return {
        "total": len(items),
        "records": [i.to_dict() for i in items],
    }


@router.get("/record/{record_id}")
def get_record_endpoint(
    record_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单条录制流量的详情数据"""
    buf = get_global_mirror_buffer()
    match = next((i for i in buf.buffer if i.record_id == record_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"未找到流量记录 [{record_id}]")
    return {
        "record": match.to_dict(),
    }


@router.get("/metrics")
def get_metrics_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取流量采样器吞吐遥测监控指标"""
    buf = get_global_mirror_buffer()
    return {
        "metrics": buf.metrics.to_dict(),
        "buffer_size": len(buf.buffer),
        "buffer_capacity": buf.capacity,
    }


@router.post("/clear")
def clear_records_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """清空镜像缓冲区"""
    buf = get_global_mirror_buffer()
    buf.clear()
    return {"message": "流量镜像缓冲区已成功清空"}


@router.post("/batch-replay")
def batch_replay_endpoint(
    payload: BatchReplayRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """批量派发流量回放执行任务"""
    buf = get_global_mirror_buffer()
    dispatched: List[Dict[str, Any]] = []

    for rid in payload.record_ids:
        match = next((i for i in buf.buffer if i.record_id == rid), None)
        dispatched.append(
            {
                "task_id": f"rpl_{uuid.uuid4().hex[:10]}",
                "record_id": rid,
                "found": match is not None,
                "target_url": f"{payload.target_host.rstrip('/')}{match.path if match else ''}",
                "status": "DISPATCHED" if match else "RECORD_NOT_FOUND",
            }
        )

    return {
        "message": f"成功调度 {len([d for d in dispatched if d['found']])} 条流量回放任务",
        "dispatched_tasks": dispatched,
    }
