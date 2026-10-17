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
from app.services.traffic_response_diff_comparator import (
    DiffSeverity,
    ResponseDiffCategory,
    ResponseDiffItem,
    compare_traffic_responses,
)
from app.services.dynamic_noise_suppressor import (
    NoiseSuppressionRule,
    NoiseType,
    match_custom_rule,
    suppress_traffic_diff_noise,
)
from app.services.replay_drift_evaluator import evaluate_replay_drift
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


class TestNoiseRuleRequest(BaseModel):
    rule: Dict[str, Any] = Field(..., description="噪声抑制规则定义")
    test_json_path: str = Field(..., description="测试目标 JSONPath")
    test_baseline_value: Any = Field(None, description="测试基线取值")
    test_replayed_value: Any = Field(None, description="测试回放取值")


class DiffEvaluateRequest(BaseModel):
    record_id: str = Field("rec_live_01", description="流量记录 ID")
    baseline_status_code: int = Field(200, description="基线状态码")
    baseline_body: Any = Field(..., description="基线响应体")
    replayed_status_code: int = Field(200, description="回放状态码")
    replayed_body: Any = Field(..., description="回放响应体")
    custom_rules: Optional[List[Dict[str, Any]]] = Field(None, description="自定义噪声规则列表")


@router.post("/noise-rule/test")
def test_noise_rule_endpoint(
    payload: TestNoiseRuleRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """在线仿真测试噪声规则是否能正确命中目标差异"""
    rule_dict = payload.rule
    rule = NoiseSuppressionRule(
        rule_id=rule_dict.get("rule_id", "test_rule"),
        name=rule_dict.get("name", "测试规则"),
        noise_type=NoiseType(rule_dict.get("noise_type", "CUSTOM_RULE")),
        path_pattern=rule_dict.get("path_pattern"),
        regex_pattern=rule_dict.get("regex_pattern"),
        enabled=rule_dict.get("enabled", True),
    )

    dummy_diff = ResponseDiffItem(
        diff_id="d_test",
        category=ResponseDiffCategory.VALUE_MISMATCH,
        severity=DiffSeverity.MINOR,
        json_path=payload.test_json_path,
        baseline_value=payload.test_baseline_value,
        replayed_value=payload.test_replayed_value,
        message="test diff",
    )

    matched = match_custom_rule(dummy_diff, rule)
    reason = "命中规则过滤条件" if matched else "未命中规则的路径或正则模式"
    return {
        "matched": matched,
        "reason": reason,
        "rule_summary": rule.to_dict(),
    }


@router.post("/diff-evaluate")
def diff_evaluate_endpoint(
    payload: DiffEvaluateRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """一站式完成差异比对、噪声自适应过滤与一致性裁决"""
    raw_diff = compare_traffic_responses(
        record_id=payload.record_id,
        baseline_status_code=payload.baseline_status_code,
        baseline_body=payload.baseline_body,
        replayed_status_code=payload.replayed_status_code,
        replayed_body=payload.replayed_body,
    )

    rules = [
        NoiseSuppressionRule(
            rule_id=r.get("rule_id", f"r_{uuid.uuid4().hex[:6]}"),
            name=r.get("name", "自定义规则"),
            noise_type=NoiseType(r.get("noise_type", "CUSTOM_RULE")),
            path_pattern=r.get("path_pattern"),
            regex_pattern=r.get("regex_pattern"),
            enabled=r.get("enabled", True),
        )
        for r in (payload.custom_rules or [])
    ]

    suppressed = suppress_traffic_diff_noise(raw_diff, custom_rules=rules)
    eval_res = evaluate_replay_drift(suppressed)

    return {
        "raw_diff_report": raw_diff.to_dict(),
        "suppressed_report": suppressed.to_dict(),
        "evaluation_result": eval_res.to_dict(),
    }
