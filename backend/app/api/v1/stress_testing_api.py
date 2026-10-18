"""全链路影子压测管控与发压作业 REST API (T1.3)

挂载至 /api/v1/stress-testing/*，提供:
1. GET /api/v1/stress-testing/rules (查询影子压测隔离规则列表);
2. POST /api/v1/stress-testing/rules (创建/注册影子压测规则);
3. POST /api/v1/stress-testing/plans/generate-step (生成标准阶梯爬坡发压计划);
4. POST /api/v1/stress-testing/workers/allocation (计算分布式 Worker 节点副本数与并发分配);
5. POST /api/v1/stress-testing/evaluations/progression (评估阶梯发压阶段自适应进阶与过载判定);
6. POST /api/v1/stress-testing/emergency-stop (一键紧急泄压急停断路)。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.stress_load_profile_stepper import (
    StressLoadProfileType,
    StressStepStage,
    StressLoadPlan,
    calculate_distributed_worker_allocation,
    evaluate_stress_step_progression,
    generate_standard_step_ramp_plan,
)
from app.services.stress_traffic_isolation_engine import (
    StressIsolationRule,
    StressTrafficRuleType,
    get_global_stress_manager,
    inspect_stress_write_safety,
)

router = APIRouter(prefix="/stress-testing", tags=["stress-testing"])


class CreateStressRuleRequest(BaseModel):
    name: str = Field(..., description="规则名称")
    rule_type: str = Field(
        default="HEADER_FLAG",
        description="规则类型: HEADER_FLAG | TENANT_STRESS | URL_PATH_MATCH | VIRTUAL_USER_RANGE",
    )
    target_service: str = Field(..., description="目标微服务")
    target_path_pattern: str = Field(default=".*", description="目标 URL 路径正则")
    tenant_id: Optional[str] = Field(default=None, description="绑定的测试租户标识")
    is_enabled: bool = Field(default=True, description="是否即时启用")
    shadow_table_suffix: str = Field(default="_shadow", description="影子表识别后缀")
    shadow_topic_suffix: str = Field(default="_shadow", description="影子 Topic 后缀")


class GenerateStepPlanRequest(BaseModel):
    target_service: str = Field(default="payment-service", description="目标微服务")
    initial_vu: int = Field(default=500, description="初始阶梯并发用户数")
    step_vu: int = Field(default=1000, description="每阶段递增并发数")
    steps_count: int = Field(default=5, description="阶梯总级数")
    stage_duration_seconds: int = Field(default=60, description="单阶段持续秒数")


class WorkerAllocationRequest(BaseModel):
    target_peak_vu: int = Field(..., description="规划的最高峰值并发用户数")
    plan_id: Optional[str] = Field(default=None, description="绑定的发压计划 ID")
    max_vu_per_worker: int = Field(default=2000, description="单节点最大承载并发数")


class EvaluateProgressionRequest(BaseModel):
    plan_dict: Dict[str, Any] = Field(..., description="发压计划结构体")
    current_stage_index: int = Field(..., description="当前阶梯编号 (1-based)")
    stage_elapsed_seconds: int = Field(..., description="当前阶段已执行时长 (秒)")
    current_error_rate_pct: float = Field(default=0.0, description="当前采样错误率百分比")
    error_rate_threshold_pct: float = Field(default=1.0, description="触发过载熔断错误率阈值")


class EmergencyStopRequest(BaseModel):
    target_service: str = Field(..., description="需要紧急急停泄压的目标服务")
    reason: str = Field(default="指标异常超标紧急泄压", description="急停原因")


class ValidateTargetRequest(BaseModel):
    target_table_or_topic: str = Field(..., description="待校验的库表或Topic名称")


@router.get("/rules", summary="查询影子压测隔离规则列表")
def list_stress_rules(target_service: Optional[str] = None) -> Dict[str, Any]:
    mgr = get_global_stress_manager()
    rules = mgr.list_rules(target_service=target_service)
    return {
        "status": "success",
        "total": len(rules),
        "rules": [r.to_dict() for r in rules],
    }


@router.post("/rules", summary="创建/注册影子压测隔离规则")
def create_stress_rule(req: CreateStressRuleRequest) -> Dict[str, Any]:
    mgr = get_global_stress_manager()
    try:
        rtype = StressTrafficRuleType(req.rule_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的规则类型: {req.rule_type}，有效值为: {[e.value for e in StressTrafficRuleType]}",
        )

    rule_id = f"st_rule_{uuid.uuid4().hex[:8]}"
    rule = StressIsolationRule(
        rule_id=rule_id,
        name=req.name,
        rule_type=rtype,
        target_service=req.target_service,
        target_path_pattern=req.target_path_pattern,
        tenant_id=req.tenant_id,
        is_enabled=req.is_enabled,
        shadow_table_suffix=req.shadow_table_suffix,
        shadow_topic_suffix=req.shadow_topic_suffix,
    )
    mgr.add_rule(rule)
    return {
        "status": "success",
        "message": f"成功创建影子压测规则: {rule.name}",
        "rule": rule.to_dict(),
    }


@router.post("/plans/generate-step", summary="生成标准五阶梯递进爬坡发压计划")
def generate_step_plan(req: GenerateStepPlanRequest) -> Dict[str, Any]:
    plan = generate_standard_step_ramp_plan(
        target_service=req.target_service,
        initial_vu=req.initial_vu,
        step_vu=req.step_vu,
        steps_count=req.steps_count,
        stage_duration_seconds=req.stage_duration_seconds,
    )
    return {
        "status": "success",
        "plan": plan.to_dict(),
    }


@router.post("/workers/allocation", summary="计算发压集群所需的分布式节点数与并发分配")
def calculate_worker_nodes(req: WorkerAllocationRequest) -> Dict[str, Any]:
    alloc = calculate_distributed_worker_allocation(
        target_peak_vu=req.target_peak_vu,
        plan_id=req.plan_id,
        max_vu_per_worker=req.max_vu_per_worker,
    )
    return {
        "status": "success",
        "allocation": alloc.to_dict(),
    }


@router.post("/evaluations/progression", summary="评估阶梯发压阶段自适应进阶与过载判定")
def evaluate_progression(req: EvaluateProgressionRequest) -> Dict[str, Any]:
    p_data = req.plan_dict
    try:
        stages = [
            StressStepStage(
                stage_index=s["stage_index"],
                stage_name=s["stage_name"],
                target_vu_count=s["target_vu_count"],
                duration_seconds=s["duration_seconds"],
                expected_tps_ceiling=s["expected_tps_ceiling"],
                ramp_up_seconds=s.get("ramp_up_seconds", 10),
            )
            for s in p_data.get("stages", [])
        ]
        plan = StressLoadPlan(
            plan_id=p_data.get("plan_id", "plan_temp"),
            plan_name=p_data.get("plan_name", "临时计划"),
            target_service=p_data.get("target_service", "order-service"),
            profile_type=StressLoadProfileType(p_data.get("profile_type", "STEP_RAMP_UP")),
            stages=stages,
            total_duration_seconds=p_data.get("total_duration_seconds", 300),
            peak_vu_count=p_data.get("peak_vu_count", 5000),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"反序列化发压计划失败: {str(e)}")

    verdict = evaluate_stress_step_progression(
        plan=plan,
        current_stage_index=req.current_stage_index,
        stage_elapsed_seconds=req.stage_elapsed_seconds,
        current_error_rate_pct=req.current_error_rate_pct,
        error_rate_threshold_pct=req.error_rate_threshold_pct,
    )
    return {
        "status": "success",
        "verdict": verdict.to_dict(),
    }


@router.post("/emergency-stop", summary="一键紧急泄压急停与压测流量切断")
def emergency_stop(req: EmergencyStopRequest) -> Dict[str, Any]:
    mgr = get_global_stress_manager()
    rules = mgr.list_rules(target_service=req.target_service)
    disabled_count = 0
    for r in rules:
        if r.is_enabled:
            r.is_enabled = False
            disabled_count += 1

    return {
        "status": "success",
        "action": "EMERGENCY_STOP_EXECUTED",
        "target_service": req.target_service,
        "disabled_rules_count": disabled_count,
        "reason": req.reason,
        "message": f"已对服务 [{req.target_service}] 成功执行紧急泄压急停，已强制切断并禁用 {disabled_count} 条活跃压测规则！",
    }


@router.post("/validate-target", summary="校验压测写操作目标是否安全隔离在影子存储")
def validate_target(req: ValidateTargetRequest) -> Dict[str, Any]:
    safe, msg = inspect_stress_write_safety(req.target_table_or_topic)
    return {
        "status": "success",
        "is_safe": safe,
        "message": msg,
        "target": req.target_table_or_topic,
    }
