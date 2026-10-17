"""全链路金丝雀灰度校验与流量染色 REST API (T1.3)

挂载至 /api/v1/canary-verification/*，提供:
1. GET /api/v1/canary-verification/rules (查询染色规则列表);
2. POST /api/v1/canary-verification/rule (注册新染色规则);
3. POST /api/v1/canary-verification/evaluate-coloration (在线模拟请求染色判定);
4. POST /api/v1/canary-verification/compare-tracks (金丝雀与基线双轨指标实时对比推演);
5. POST /api/v1/canary-verification/rollback (一键紧急切流与版本回滚)。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.canary_baseline_metric_comparator import (
    TrackMetricsSample,
    compare_canary_and_baseline_tracks,
)
from app.services.canary_traffic_coloration_engine import (
    CanaryColorationRule,
    ColorationRuleType,
    get_global_canary_manager,
)

router = APIRouter(prefix="/canary-verification", tags=["canary-verification"])


class CreateColorationRuleRequest(BaseModel):
    name: str = Field(..., description="规则名称")
    rule_type: str = Field(
        ..., description="规则类型: HTTP_HEADER | COOKIE_PARAM | USER_MODULO | TENANT_WHITELIST | WEIGHT_RANDOM"
    )
    target_service: str = Field(..., description="目标微服务")
    canary_version_tag: str = Field(..., description="金丝雀版本号标识，如 v2.1.0-canary")
    match_key: str = Field(default="", description="匹配键 (Header名或Cookie名)")
    match_value: str = Field(default="", description="匹配值")
    weight_pct: float = Field(default=10.0, description="分流百分比权重 (1~100)")
    is_enabled: bool = Field(default=True, description="是否即时启用")


class EvaluateColorationRequest(BaseModel):
    headers: Optional[Dict[str, str]] = Field(default=None, description="模拟请求头")
    cookies: Optional[Dict[str, str]] = Field(default=None, description="模拟 Cookie")
    user_id: Optional[str] = Field(default=None, description="模拟用户唯一标识")
    tenant_id: Optional[str] = Field(default=None, description="模拟租户标识")
    target_service: Optional[str] = Field(default=None, description="目标微服务")


class CompareTracksRequest(BaseModel):
    baseline_metrics: Dict[str, Any] = Field(..., description="基线稳定版本指标采样")
    canary_metrics: Dict[str, Any] = Field(..., description="金丝雀候选版本指标采样")
    target_service: str = Field(default="payment-service", description="目标微服务")
    error_rate_tolerance: float = Field(default=1.5, description="错误率偏离容差百分比")
    latency_ratio_tolerance: float = Field(default=1.25, description="P99延迟偏离倍数容差")


class EmergencyRollbackRequest(BaseModel):
    target_service: str = Field(..., description="需要紧急回滚的目标服务")
    reason: str = Field(default="指标异常击穿熔断", description="回滚触发原因")


@router.get("/rules", summary="查询染色规则列表")
def list_coloration_rules(target_service: Optional[str] = None) -> List[Dict[str, Any]]:
    mgr = get_global_canary_manager()
    rules = mgr.list_rules(target_service=target_service)
    return [r.to_dict() for r in rules]


@router.post("/rule", summary="注册新染色规则")
def create_coloration_rule(req: CreateColorationRuleRequest) -> Dict[str, Any]:
    mgr = get_global_canary_manager()
    try:
        r_type = ColorationRuleType(req.rule_type.strip().upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的染色规则类型 [{req.rule_type}], 可选: {[e.value for e in ColorationRuleType]}",
        )

    rule_id = f"crule_{uuid.uuid4().hex[:8]}"
    rule = CanaryColorationRule(
        rule_id=rule_id,
        name=req.name,
        rule_type=r_type,
        target_service=req.target_service,
        canary_version_tag=req.canary_version_tag,
        match_key=req.match_key,
        match_value=req.match_value,
        weight_pct=req.weight_pct,
        is_enabled=req.is_enabled,
    )
    mgr.add_rule(rule)
    return rule.to_dict()


@router.post("/evaluate-coloration", summary="在线模拟请求染色判定")
def evaluate_coloration(req: EvaluateColorationRequest) -> Dict[str, Any]:
    mgr = get_global_canary_manager()
    ctx = mgr.evaluate_traffic_coloration(
        headers=req.headers,
        cookies=req.cookies,
        user_id=req.user_id,
        tenant_id=req.tenant_id,
        target_service=req.target_service,
    )
    return ctx.to_dict()


@router.post("/compare-tracks", summary="金丝雀与基线双轨指标实时对比推演")
def compare_tracks_endpoint(req: CompareTracksRequest) -> Dict[str, Any]:
    b_dict = req.baseline_metrics
    c_dict = req.canary_metrics

    base_sample = TrackMetricsSample(
        track_name=b_dict.get("track_name", "baseline"),
        version_tag=b_dict.get("version_tag", "v1.0.0"),
        total_requests=b_dict.get("total_requests", 10000),
        error_requests=b_dict.get("error_requests", 10),
        error_rate_pct=b_dict.get("error_rate_pct", 0.1),
        success_rate_pct=b_dict.get("success_rate_pct", 99.9),
        p99_latency_ms=b_dict.get("p99_latency_ms", 120.0),
        avg_latency_ms=b_dict.get("avg_latency_ms", 35.0),
        cpu_usage_pct=b_dict.get("cpu_usage_pct", 25.0),
        mem_usage_mb=b_dict.get("mem_usage_mb", 512.0),
    )

    canary_sample = TrackMetricsSample(
        track_name=c_dict.get("track_name", "canary"),
        version_tag=c_dict.get("version_tag", "v1.1.0-canary"),
        total_requests=c_dict.get("total_requests", 1000),
        error_requests=c_dict.get("error_requests", 5),
        error_rate_pct=c_dict.get("error_rate_pct", 0.5),
        success_rate_pct=c_dict.get("success_rate_pct", 99.5),
        p99_latency_ms=c_dict.get("p99_latency_ms", 130.0),
        avg_latency_ms=c_dict.get("avg_latency_ms", 38.0),
        cpu_usage_pct=c_dict.get("cpu_usage_pct", 28.0),
        mem_usage_mb=c_dict.get("mem_usage_mb", 520.0),
    )

    report = compare_canary_and_baseline_tracks(
        baseline=base_sample,
        canary=canary_sample,
        target_service=req.target_service,
        error_rate_tolerance_diff_pct=req.error_rate_tolerance,
        latency_ratio_tolerance=req.latency_ratio_tolerance,
    )
    return report.to_dict()


@router.post("/rollback", summary="一键紧急切流与版本回滚")
def emergency_rollback(req: EmergencyRollbackRequest) -> Dict[str, Any]:
    mgr = get_global_canary_manager()
    disabled_count = 0

    # 紧急切断该微服务所有启用的金丝雀染色规则
    for r in mgr.list_rules(target_service=req.target_service):
        if r.is_enabled:
            r.is_enabled = False
            r.weight_pct = 0.0
            disabled_count += 1

    return {
        "status": "ROLLBACK_COMPLETED",
        "target_service": req.target_service,
        "reason": req.reason,
        "canary_traffic_weight_pct": 0.0,
        "disabled_rules_count": disabled_count,
        "message": f"已紧急拔除 [{req.target_service}] 所有的金丝雀染色分流规则，100% 流量已秒级回退至基线稳定态！",
        "timestamp": "now",
    }
