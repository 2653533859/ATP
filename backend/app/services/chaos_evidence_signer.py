"""混沌实验结论与韧性得分 64 位 SHA-256 存证证书器服务 (T4.2)

为混沌演练全生命周期产物（稳态基线、故障注入、断路器 RTO 评级、韧性雷达分与加固策略）提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, compact separators);
2. 64 字符十六进制 SHA-256 存证防篡改指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (ChaosEvidenceCertificate: VALID | TAMPERED_INVALID)。
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.architecture_weakness_radar import ArchitectureResilienceRadarReport
from app.services.chaos_steady_state_evaluator import ChaosExperimentSession
from app.services.resilience_rto_evaluator import ResilienceRTOEvaluation


class ChaosArtifactType(str, enum.Enum):
    STEADY_STATE_BASELINE = "STEADY_STATE_BASELINE"  # 稳态基线假说定义产物
    FAULT_INJECTION_RECORD = "FAULT_INJECTION_RECORD"  # 故障注入与演练执行记录
    RESILIENCE_RTO_EVALUATION = "RESILIENCE_RTO_EVALUATION"  # 断路器熔断与自愈 RTO 评定报告
    RADAR_HARDENING_REPORT = "RADAR_HARDENING_REPORT"  # 架构五维韧性雷达分析与加固策略报告


class ChaosVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或指纹被篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class ChaosEvidenceCertificate:
    certificate_id: str
    artifact_type: ChaosArtifactType
    artifact_id: str
    experiment_id: str
    signer_identity: str
    algorithm: str  # SHA-256/HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256 摘要
    hmac_signature: str
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_CHAOS_CERT_STORE: Dict[str, ChaosEvidenceCertificate] = {}
_DEFAULT_CHAOS_SECRET = b"atp-v5-8-0-chaos-engineering-evidence-secret-2026"


def clear_chaos_certificates() -> None:
    """清空存证证书内存库（测试隔离使用）"""
    _CHAOS_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算规范化 JSON 数据的 64 位 SHA-256 哈希指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_hmac_signature(evidence_sha256: str, secret_key: bytes = _DEFAULT_CHAOS_SECRET) -> str:
    """对 SHA-256 哈希指纹生成平台权威防伪 HMAC 签名"""
    return hmac.new(secret_key, evidence_sha256.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_chaos_artifact(
    artifact_type: ChaosArtifactType,
    artifact_id: str,
    experiment_id: str,
    payload: Dict[str, Any],
    summary: Dict[str, Any],
    signer_identity: str = "ATP-CHAOS-EVIDENCE-AUTHORITY-v5.8.0",
    secret_key: bytes = _DEFAULT_CHAOS_SECRET,
) -> ChaosEvidenceCertificate:
    """通用混沌演练产物存证证书签发"""
    cert_id = f"cert_chaos_{uuid.uuid4().hex[:12]}"
    canonical_json = canonicalize_payload(payload)
    sha256_hash = compute_evidence_sha256(canonical_json)
    signature = compute_hmac_signature(sha256_hash, secret_key=secret_key)

    cert = ChaosEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        experiment_id=experiment_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=signature,
        canonical_payload=payload,
        summary=summary,
    )
    _CHAOS_CERT_STORE[cert_id] = cert
    return cert


def sign_steady_state_baseline(experiment: ChaosExperimentSession) -> ChaosEvidenceCertificate:
    """为混沌实验稳态基线定义签发存证证书"""
    payload = {
        "experiment_id": experiment.experiment_id,
        "name": experiment.name,
        "target_service": experiment.target_service,
        "hypothesis": asdict(experiment.hypothesis),
    }
    summary = {
        "target_service": experiment.target_service,
        "max_p99_latency_ms": experiment.hypothesis.max_p99_latency_ms,
        "min_success_rate_pct": experiment.hypothesis.min_success_rate_pct,
    }
    return sign_chaos_artifact(
        artifact_type=ChaosArtifactType.STEADY_STATE_BASELINE,
        artifact_id=experiment.experiment_id,
        experiment_id=experiment.experiment_id,
        payload=payload,
        summary=summary,
    )


def sign_resilience_rto_evaluation(evaluation: ResilienceRTOEvaluation) -> ChaosEvidenceCertificate:
    """为断路器 RTO 韧性评估报告签发存证证书"""
    payload = evaluation.to_dict()
    summary = {
        "evaluation_id": evaluation.evaluation_id,
        "target_service": evaluation.target_service,
        "resilience_grade": evaluation.resilience_grade.value,
        "circuit_breaker_trip_time_ms": evaluation.circuit_breaker_trip_time_ms,
        "recovery_time_objective_seconds": evaluation.recovery_time_objective_seconds,
        "is_slo_compliant": evaluation.is_slo_compliant,
    }
    return sign_chaos_artifact(
        artifact_type=ChaosArtifactType.RESILIENCE_RTO_EVALUATION,
        artifact_id=evaluation.evaluation_id,
        experiment_id=evaluation.experiment_id,
        payload=payload,
        summary=summary,
    )


def sign_radar_hardening_report(report: ArchitectureResilienceRadarReport) -> ChaosEvidenceCertificate:
    """为架构五维韧性雷达分析与加固报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "report_id": report.report_id,
        "target_service": report.target_service,
        "composite_resilience_score": report.composite_resilience_score,
        "identified_weaknesses_count": report.identified_weaknesses_count,
        "recommendations_count": len(report.recommendations),
    }
    return sign_chaos_artifact(
        artifact_type=ChaosArtifactType.RADAR_HARDENING_REPORT,
        artifact_id=report.report_id,
        experiment_id=report.experiment_id,
        payload=payload,
        summary=summary,
    )


def verify_chaos_certificate(
    certificate_id: str,
    secret_key: bytes = _DEFAULT_CHAOS_SECRET,
) -> Tuple[ChaosVerificationVerdict, str]:
    """验证混沌存证证书的 SHA-256 指纹完整性与 HMAC 数字签名防伪真实性"""
    cert = _CHAOS_CERT_STORE.get(certificate_id)
    if not cert:
        return (
            ChaosVerificationVerdict.CERTIFICATE_NOT_FOUND,
            f"存证证书库中未检索到证书 ID [{certificate_id}]",
        )

    # 1. 重新计算当前 payload 的确定性 SHA-256 指纹
    current_canonical = canonicalize_payload(cert.canonical_payload)
    recalculated_sha256 = compute_evidence_sha256(current_canonical)

    if recalculated_sha256 != cert.evidence_sha256:
        return (
            ChaosVerificationVerdict.TAMPERED_INVALID,
            f"存证数据指纹不匹配: 原始 [{cert.evidence_sha256}] vs 当前计算 [{recalculated_sha256}]，数据已被篡改！",
        )

    # 2. 重新验证平台 HMAC-SHA256 签名真实性
    expected_sig = compute_hmac_signature(cert.evidence_sha256, secret_key=secret_key)
    if not hmac.compare_digest(expected_sig, cert.hmac_signature):
        return (
            ChaosVerificationVerdict.TAMPERED_INVALID,
            "平台 HMAC 数字签名无效或由非可信私钥伪造，判定为非法证书！",
        )

    return (
        ChaosVerificationVerdict.VALID,
        f"证书 [{certificate_id}] 验签成功：64 位 SHA-256 指纹与 HMAC 权威签名双重校验通过，数据绝对真实未被篡改。",
    )


def get_chaos_certificate(certificate_id: str) -> Optional[ChaosEvidenceCertificate]:
    """获取指定存证证书"""
    return _CHAOS_CERT_STORE.get(certificate_id)


def list_chaos_certificates(experiment_id: Optional[str] = None) -> List[ChaosEvidenceCertificate]:
    """列出存证证书列表，支持按实验 ID 过滤"""
    certs = list(_CHAOS_CERT_STORE.values())
    if experiment_id:
        return [c for c in certs if c.experiment_id == experiment_id]
    return sorted(certs, key=lambda c: c.issued_at, reverse=True)
