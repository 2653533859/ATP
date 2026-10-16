"""Software Quality Governance & Multi-Dimensional Health Metrics REST API Router (C4.1)."""

from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.quality_metrics_engine import compute_quality_health_report
from app.services.quality_gate_engine import (
    QualityGateProfile,
    QualityGateRule,
    evaluate_quality_gate,
    list_gate_profiles,
    register_gate_profile,
)
from app.services.release_readiness_certification import (
    generate_release_certificate,
    get_certificate,
    verify_certificate_authenticity,
)

router = APIRouter(prefix="/quality", tags=["企业级测试质量度量与门禁中心"])


class EvaluateQualityMetricsIn(BaseModel):
    project_id: int = Field(ge=1, description="项目 ID")
    total_cases: int = Field(default=100, ge=1, description="测试用例总数")
    automated_cases: int = Field(default=85, ge=0, description="已实现自动化用例数")
    internal_defects: int = Field(default=40, ge=0, description="测试阶段发现的内部缺陷数")
    prod_escapes: int = Field(default=2, ge=0, description="线上逃逸生产缺陷数")
    total_runs: int = Field(default=50, ge=1, description="近期评估的测试执行总轮次")
    flaky_runs: int = Field(default=2, ge=0, description="包含波动或 Flaky 结果的执行轮次")
    mttr_hours: float = Field(default=3.5, ge=0.1, description="平均缺陷修复用时 (小时)")


class CreateGateProfileIn(BaseModel):
    profile_id: str = Field(min_length=2, max_length=64, description="门禁策略标识")
    name: str = Field(min_length=1, max_length=128, description="门禁策略名称")
    description: str = Field(default="", description="策略描述")
    rules: list[dict[str, Any]] = Field(min_length=1, description="门禁规则列表")
    block_on_failure: bool = Field(default=True, description="未达标时是否阻塞 CI 流程")


class EvaluateGateIn(BaseModel):
    profile_id: str = Field(default="gate_prod_release", description="执行判定的门禁策略 ID")
    metrics: dict[str, Any] = Field(..., description="待判定的各维度指标键值对")


class GenerateCertificateIn(BaseModel):
    project_id: int = Field(ge=1, description="项目 ID")
    release_version: str = Field(min_length=1, max_length=64, description="待发布的版本号 (如 v3.2.0)")
    commit_sha: str = Field(min_length=6, max_length=64, description="对应代码 Commit SHA")
    target_environment: str = Field(default="production", description="目标发版环境")
    gate_profile_id: str = Field(default="gate_prod_release", description="质量门禁策略 ID")
    metrics_override: dict[str, Any] | None = None


class VerifyCertificateIn(BaseModel):
    certificate_id: str = Field(description="证书编号")
    release_version: str = Field(description="版本号")
    commit_sha: str = Field(description="Commit SHA")
    verdict: str = Field(description="评定决议")
    quality_score: float = Field(description="质量综合得分")
    issued_at: str = Field(description="签发时间戳")
    digital_seal_signature: str = Field(description="待验证的防伪数字印章签名")


@router.get("/metrics/project/{project_id}")
async def get_project_quality_metrics_endpoint(
    project_id: int,
    _user: User = Depends(get_current_user),
):
    """获取指定项目的全生命周期质量度量大盘与发版准入评估结果。"""
    _ = _user
    report = compute_quality_health_report(project_id=project_id)
    return report.to_dict()


@router.post("/metrics/evaluate")
async def evaluate_custom_quality_metrics_endpoint(
    body: EvaluateQualityMetricsIn,
    _user: User = Depends(get_current_user),
):
    """基于自定义度量参数推算四维加权质量健康得分与风险预警。"""
    _ = _user
    report = compute_quality_health_report(
        project_id=body.project_id,
        total_cases=body.total_cases,
        automated_cases=body.automated_cases,
        internal_defects=body.internal_defects,
        prod_escapes=body.prod_escapes,
        total_runs=body.total_runs,
        flaky_runs=body.flaky_runs,
        mttr_hours=body.mttr_hours,
    )
    return report.to_dict()


@router.get("/gates/profiles")
async def list_gate_profiles_endpoint(
    _user: User = Depends(get_current_user),
):
    """获取平台已配置的所有 CI/CD 质量门禁基线与策略档案。"""
    _ = _user
    profiles = list_gate_profiles()
    return {"total": len(profiles), "profiles": [p.to_dict() for p in profiles]}


@router.post("/gates/profiles")
async def register_gate_profile_endpoint(
    body: CreateGateProfileIn,
    _user: User = Depends(require_engineer),
):
    """创建或注册自定义 CI/CD 质量门禁策略 (需工程师权限)。"""
    _ = _user
    rules_list: list[QualityGateRule] = []
    for r in body.rules:
        rule = QualityGateRule(
            metric_key=str(r.get("metric_key", "")),
            operator=str(r.get("operator", "gte")),
            threshold=float(r.get("threshold", 0.0)),
            severity=str(r.get("severity", "blocker")),
            description=str(r.get("description", "")),
        )
        rules_list.append(rule)

    profile = QualityGateProfile(
        profile_id=body.profile_id,
        name=body.name,
        description=body.description,
        rules=rules_list,
        block_on_failure=body.block_on_failure,
    )
    register_gate_profile(profile)
    return {"message": "质量门禁策略注册成功", "profile": profile.to_dict()}


@router.post("/gates/evaluate")
async def evaluate_quality_gate_endpoint(
    body: EvaluateGateIn,
    _user: User = Depends(get_current_user),
):
    """在线评估当前流水线指标是否满足质量门禁准入要求 (返回 PASSED / BLOCKED 及非零退出码)。"""
    _ = _user
    try:
        result = evaluate_quality_gate(body.profile_id, body.metrics)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/certification/generate")
async def generate_release_certificate_endpoint(
    body: GenerateCertificateIn,
    _user: User = Depends(require_engineer),
):
    """聚合全生命周期质量指标与门禁决策，生成防伪发版准入合格证书。"""
    _ = _user
    cert = generate_release_certificate(
        project_id=body.project_id,
        release_version=body.release_version,
        commit_sha=body.commit_sha,
        target_environment=body.target_environment,
        gate_profile_id=body.gate_profile_id,
        metrics_override=body.metrics_override,
    )
    return cert.to_dict()


@router.post("/certification/verify")
async def verify_certificate_authenticity_endpoint(
    body: VerifyCertificateIn,
    _user: User = Depends(get_current_user),
):
    """校验发版准入证书的 HMAC-SHA256 数字防伪印章真实性，杜绝伪造篡改。"""
    _ = _user
    return verify_certificate_authenticity(
        certificate_id=body.certificate_id,
        release_version=body.release_version,
        commit_sha=body.commit_sha,
        verdict=body.verdict,
        quality_score=body.quality_score,
        issued_at=body.issued_at,
        digital_seal_signature=body.digital_seal_signature,
    )


@router.get("/certification/{certificate_id}")
async def get_certificate_endpoint(
    certificate_id: str,
    _user: User = Depends(get_current_user),
):
    """获取指定发版准入合格证书的完整审计凭证与签名快照。"""
    _ = _user
    cert = get_certificate(certificate_id)
    if not cert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"发版证书不存在: {certificate_id}")
    return cert.to_dict()
