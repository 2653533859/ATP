"""全链路分布式混沌工程与弹性韧性攻防演练 REST API (T1.3)

为微服务故障注入、混沌实验编排、稳态健康探测与即时恢复提供标准化 RESTful 端点:
1. 故障注入算子规则库管理与查询 (/chaos-engineering/fault-rules, /fault-rule);
2. 混沌演练实验创建与检索 (/chaos-engineering/experiments, /experiment/{id});
3. 故障注入一键触发与即时终止恢复 (/chaos-engineering/experiment/{id}/trigger, /stop);
4. 在线指标采样写入与稳态流式评估 (/chaos-engineering/experiment/{id}/sample);
5. 单请求故障注入仿真演算 (/chaos-engineering/fault-inject/simulate)。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.chaos_fault_injector_library import (
    ChaosFaultConfig,
    ChaosFaultType,
    apply_chaos_fault_injection,
    get_global_fault_library,
)
from app.services.chaos_steady_state_evaluator import (
    ChaosExperimentState,
    SteadyStateHypothesis,
    create_steady_state_sample,
    get_global_chaos_manager,
)

router = APIRouter(prefix="/chaos-engineering", tags=["Distributed Chaos Engineering & Resilience Drill"])


class CreateFaultRuleRequest(BaseModel):
    name: str = Field(..., description="故障规则名称")
    fault_type: ChaosFaultType = Field(..., description="故障算子类型")
    target_pattern: str = Field("*/orders/*", description="URL Glob 目标通配符")
    latency_ms: float = Field(0.0, ge=0.0, description="基准延迟毫秒")
    jitter_ms: float = Field(0.0, ge=0.0, description="抖动毫秒")
    loss_percentage: float = Field(0.0, ge=0.0, le=100.0, description="丢包百分比")
    mutated_status_code: int = Field(500, description="变异 HTTP 状态码")
    effective_probability: float = Field(1.0, ge=0.0, le=1.0, description="触发概率")
    description: str = Field("", description="规则说明")


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., description="混沌实验名称")
    target_service: str = Field(..., description="目标服务标识")
    fault_id: str = Field(..., description="关联故障算子规则 ID")
    min_success_rate_pct: float = Field(98.0, ge=0.0, le=100.0, description="最低稳态成功率要求")
    max_p99_latency_ms: float = Field(400.0, ge=0.0, description="最高允许 P99 延迟")
    require_probe_healthy: bool = Field(True, description="是否要求探针始终健康")


class RecordSampleRequest(BaseModel):
    total_requests: int = Field(..., ge=1, description="采样周期内请求总量")
    failed_requests: int = Field(0, ge=0, description="失败请求数量")
    p99_latency_ms: float = Field(100.0, ge=0.0, description="当前周期 P99 延迟")
    is_probe_healthy: bool = Field(True, description="健康检查探针是否正常")


class SimulateFaultInjectRequest(BaseModel):
    path: str = Field(..., description="请求服务路径")
    original_status_code: int = Field(200, description="原始基线状态码")
    original_body: Any = Field(None, description="原始基线响应载荷")
    fault_id: Optional[str] = Field(None, description="指定执行的故障算子 ID")
    random_seed: Optional[float] = Field(None, description="确定性测试随机种子")


@router.get("/fault-rules")
def list_fault_rules_endpoint(
    fault_type: Optional[ChaosFaultType] = None,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询故障算子库中的规则列表"""
    lib = get_global_fault_library()
    rules = lib.list_rules(fault_type=fault_type)
    return {
        "total": len(rules),
        "rules": [r.to_dict() for r in rules],
    }


@router.post("/fault-rule")
def create_fault_rule_endpoint(
    payload: CreateFaultRuleRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """注册新的混沌故障算子规则"""
    lib = get_global_fault_library()
    fid = f"cflt_{uuid.uuid4().hex[:8]}"
    config = ChaosFaultConfig(
        fault_id=fid,
        name=payload.name,
        fault_type=payload.fault_type,
        target_pattern=payload.target_pattern,
        latency_ms=payload.latency_ms,
        jitter_ms=payload.jitter_ms,
        loss_percentage=payload.loss_percentage,
        mutated_status_code=payload.mutated_status_code,
        effective_probability=payload.effective_probability,
        description=payload.description,
    )
    lib.register_rule(config)
    return {
        "message": f"成功注册故障算子规则 [{config.name}]",
        "rule": config.to_dict(),
    }


@router.post("/experiment")
def create_experiment_endpoint(
    payload: CreateExperimentRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """创建新的分布式混沌演练实验会话"""
    mgr = get_global_chaos_manager()
    hypo = SteadyStateHypothesis(
        hypothesis_id=f"hypo_{uuid.uuid4().hex[:8]}",
        target_service=payload.target_service,
        min_success_rate_pct=payload.min_success_rate_pct,
        max_p99_latency_ms=payload.max_p99_latency_ms,
        require_probe_healthy=payload.require_probe_healthy,
    )

    session = mgr.create_experiment(
        name=payload.name,
        target_service=payload.target_service,
        fault_id=payload.fault_id,
        hypothesis=hypo,
    )
    return {
        "message": f"混沌实验 [{session.name}] 创建成功",
        "experiment": session.to_dict(),
    }


@router.get("/experiments")
def list_experiments_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询所有混沌实验会话列表"""
    mgr = get_global_chaos_manager()
    experiments = mgr.list_experiments()
    return {
        "total": len(experiments),
        "experiments": [e.to_dict() for e in experiments],
    }


@router.get("/experiment/{experiment_id}")
def get_experiment_endpoint(
    experiment_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取指定混沌实验详情与最新采样监控曲线"""
    mgr = get_global_chaos_manager()
    session = mgr.get_experiment(experiment_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"未找到混沌实验 [{experiment_id}]")
    return {
        "experiment": session.to_dict(),
    }


@router.post("/experiment/{experiment_id}/trigger")
def trigger_experiment_endpoint(
    experiment_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """启动该实验的故障注入，进入演练攻防阶段"""
    mgr = get_global_chaos_manager()
    session = mgr.get_experiment(experiment_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"未找到混沌实验 [{experiment_id}]")

    session.state = ChaosExperimentState.FAULT_INJECTING
    return {
        "message": f"实验 [{session.name}] 故障注入已启动",
        "state": session.state.value,
    }


@router.post("/experiment/{experiment_id}/sample")
def record_sample_endpoint(
    experiment_id: str,
    payload: RecordSampleRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """写入实时采样指标，执行稳态判定"""
    mgr = get_global_chaos_manager()
    session = mgr.get_experiment(experiment_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"未找到混沌实验 [{experiment_id}]")

    sample = create_steady_state_sample(
        total_requests=payload.total_requests,
        failed_requests=payload.failed_requests,
        p99_latency_ms=payload.p99_latency_ms,
        is_probe_healthy=payload.is_probe_healthy,
    )

    state, violations = mgr.record_and_evaluate(experiment_id, sample)
    return {
        "state": state.value,
        "is_steady": len(violations) == 0,
        "violations": violations,
        "sample": sample.to_dict(),
    }


@router.post("/experiment/{experiment_id}/stop")
def stop_experiment_endpoint(
    experiment_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """手动终止混沌实验并恢复现场"""
    mgr = get_global_chaos_manager()
    session = mgr.stop_experiment(experiment_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"未找到混沌实验 [{experiment_id}]")
    return {
        "message": f"混沌实验 [{session.name}] 已终止并恢复现场",
        "state": session.state.value,
    }


@router.post("/fault-inject/simulate")
def simulate_fault_inject_endpoint(
    payload: SimulateFaultInjectRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """演练单个请求在指定故障注入算子下的变异执行结果"""
    lib = get_global_fault_library()
    rule = lib.get_rule(payload.fault_id) if payload.fault_id else None

    result = apply_chaos_fault_injection(
        path=payload.path,
        original_status_code=payload.original_status_code,
        original_body=payload.original_body,
        active_fault=rule,
        random_seed=payload.random_seed,
    )
    return {
        "simulation_result": result.to_dict(),
    }
