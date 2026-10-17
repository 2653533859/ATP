"""金丝雀健康度结论与放行准入 64 位 SHA-256 存证证书器服务 (T4.2)

为全链路金丝雀治理全流程产物（健康度评分、熔断回滚裁决、影子防污染报告、生产强准入）提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, compact separators);
2. 64 字符十六进制 SHA-256 存证防伪指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发、存储检索与在线合规验签防篡改探针 (CanaryEvidenceCertificate: VALID | TAMPERED_INVALID)。
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

from app.services.canary_auto_rollback_guard import CanaryRollbackGuardVerdict
from app.services.canary_data_isolation_inspector import CanaryDataIsolationReport
from app.services.canary_health_scoring_stepper import CanaryHealthScoreReport, CanarySteppingDecision
from app.services.canary_safety_boundary_guard import CanarySafetyAdmissionVerdict


class CanaryArtifactType(str, enum.Enum):
    CANARY_HEALTH_SCORE_EVALUATION = "CANARY_HEALTH_SCORE_EVALUATION"  # 五维健康度评分与自适应调度
    CANARY_ROLLBACK_GUARD_VERDICT = "CANARY_ROLLBACK_GUARD_VERDICT"  # 灰度击穿熔断与自动回滚裁决
    CANARY_DATA_ISOLATION_REPORT = "CANARY_DATA_ISOLATION_REPORT"  # 影子存储防污染与数据隔离报告
    CANARY_SAFETY_ADMISSION_VERDICT = "CANARY_SAFETY_ADMISSION_VERDICT"  # 生产环境三要素强准入放行裁决


class CanaryVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class CanaryEvidenceCertificate:
    certificate_id: str
    artifact_type: CanaryArtifactType
    artifact_id: str
    target_service: str
    signer_identity: str
    algorithm: str  # SHA-256/HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256 摘要
    hmac_signature: str
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_CANARY_CERT_STORE: Dict[str, CanaryEvidenceCertificate] = {}
_DEFAULT_CANARY_SECRET = b"atp-v6-1-0-canary-verification-evidence-secret-2026"


def clear_canary_certificates() -> None:
    """清空金丝雀存证证书内存库（测试隔离使用）"""
    _CANARY_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算规范化 JSON 数据的 64 位 SHA-256 哈希指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_hmac_signature(evidence_sha256: str, secret_key: bytes = _DEFAULT_CANARY_SECRET) -> str:
    """对 SHA-256 哈希指纹生成平台权威防伪 HMAC 签名"""
    return hmac.new(secret_key, evidence_sha256.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_canary_artifact(
    artifact_type: CanaryArtifactType,
    artifact_id: str,
    target_service: str,
    payload: Dict[str, Any],
    summary: Dict[str, Any],
    signer_identity: str = "ATP-CANARY-CONTROL-AUTHORITY-v6.1.0",
    secret_key: bytes = _DEFAULT_CANARY_SECRET,
) -> CanaryEvidenceCertificate:
    """通用金丝雀治理产物存证证书签发"""
    cert_id = f"cert_can_{uuid.uuid4().hex[:12]}"
    canonical_json = canonicalize_payload(payload)
    sha256_hash = compute_evidence_sha256(canonical_json)
    signature = compute_hmac_signature(sha256_hash, secret_key=secret_key)

    cert = CanaryEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        target_service=target_service,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=signature,
        canonical_payload=payload,
        summary=summary,
    )
    _CANARY_CERT_STORE[cert_id] = cert
    return cert


def sign_canary_stepping_decision(decision: CanarySteppingDecision) -> CanaryEvidenceCertificate:
    """为金丝雀五维健康度评分与自适应调度决策签发存证证书"""
    payload = decision.to_dict()
    summary = {
        "decision_id": decision.decision_id,
        "target_service": decision.target_service,
        "canary_version": decision.canary_version,
        "current_stage": decision.current_stage.value,
        "current_weight_pct": decision.current_weight_pct,
        "recommended_action": decision.recommended_action.value,
        "next_recommended_weight_pct": decision.next_recommended_weight_pct,
        "composite_score": decision.health_score.composite_score,
        "grade": decision.health_score.grade,
    }
    return sign_canary_artifact(
        artifact_type=CanaryArtifactType.CANARY_HEALTH_SCORE_EVALUATION,
        artifact_id=decision.decision_id,
        target_service=decision.target_service,
        payload=payload,
        summary=summary,
    )


def sign_canary_health_score(
    report: CanaryHealthScoreReport,
    target_service: str = "payment-service",
    canary_version: str = "v1.2.0-canary",
) -> CanaryEvidenceCertificate:
    """为金丝雀五维健康度评分结论签发存证证书"""
    payload = report.to_dict()
    artifact_id = f"hs_{uuid.uuid4().hex[:10]}"
    summary = {
        "artifact_id": artifact_id,
        "target_service": target_service,
        "canary_version": canary_version,
        "composite_score": report.composite_score,
        "grade": report.grade,
    }
    return sign_canary_artifact(
        artifact_type=CanaryArtifactType.CANARY_HEALTH_SCORE_EVALUATION,
        artifact_id=artifact_id,
        target_service=target_service,
        payload=payload,
        summary=summary,
    )


def sign_canary_rollback_verdict(verdict: CanaryRollbackGuardVerdict) -> CanaryEvidenceCertificate:
    """为灰度击穿熔断与自动回滚看门狗裁决签发存证证书"""
    payload = verdict.to_dict()
    summary = {
        "guard_verdict_id": verdict.guard_verdict_id,
        "target_service": verdict.target_service,
        "canary_version": verdict.canary_version,
        "is_tripped": verdict.is_tripped,
        "action": verdict.action.value,
        "disabled_rules_count": verdict.disabled_rules_count,
        "tripped_rules": verdict.tripped_rules,
    }
    return sign_canary_artifact(
        artifact_type=CanaryArtifactType.CANARY_ROLLBACK_GUARD_VERDICT,
        artifact_id=verdict.guard_verdict_id,
        target_service=verdict.target_service,
        payload=payload,
        summary=summary,
    )


def sign_canary_data_isolation(report: CanaryDataIsolationReport) -> CanaryEvidenceCertificate:
    """为影子存储数据隔离与防污染审计报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "report_id": report.report_id,
        "target_service": report.target_service,
        "total_write_events": report.total_write_events,
        "shadow_routed_count": report.shadow_routed_count,
        "leaked_master_writes_count": report.leaked_master_writes_count,
        "isolation_compliance_pct": report.isolation_compliance_pct,
        "leak_severity": report.leak_severity.value,
        "is_pollution_detected": report.is_pollution_detected,
    }
    return sign_canary_artifact(
        artifact_type=CanaryArtifactType.CANARY_DATA_ISOLATION_REPORT,
        artifact_id=report.report_id,
        target_service=report.target_service,
        payload=payload,
        summary=summary,
    )


def sign_canary_safety_admission(verdict: CanarySafetyAdmissionVerdict) -> CanaryEvidenceCertificate:
    """为生产环境灰度强准入审批看门狗放行结论签发存证证书"""
    payload = verdict.to_dict()
    summary = {
        "verdict_id": verdict.verdict_id,
        "target_service": verdict.target_service,
        "environment": verdict.environment,
        "is_admitted": verdict.is_admitted,
        "verdict_code": verdict.verdict_code.value,
        "proposed_weight_pct": verdict.proposed_weight_pct,
        "reasons": verdict.reasons,
    }
    return sign_canary_artifact(
        artifact_type=CanaryArtifactType.CANARY_SAFETY_ADMISSION_VERDICT,
        artifact_id=verdict.verdict_id,
        target_service=verdict.target_service,
        payload=payload,
        summary=summary,
    )


def get_canary_certificate(certificate_id: str) -> Optional[CanaryEvidenceCertificate]:
    """根据证书 ID 查询存证记录"""
    return _CANARY_CERT_STORE.get(certificate_id)


def list_canary_certificates(target_service: Optional[str] = None) -> List[CanaryEvidenceCertificate]:
    """查询存证证书列表，支持微服务名称过滤"""
    certs = list(_CANARY_CERT_STORE.values())
    if target_service:
        certs = [c for c in certs if c.target_service == target_service]
    return sorted(certs, key=lambda c: c.issued_at, reverse=True)


def verify_canary_certificate(
    certificate_id: str,
    secret_key: bytes = _DEFAULT_CANARY_SECRET,
) -> Tuple[CanaryVerificationVerdict, Optional[str]]:
    """防篡改合规验签探针: 重新计算 Canonical JSON、SHA-256 与 HMAC-SHA256 签名并执行恒定时间比对"""
    cert = get_canary_certificate(certificate_id)
    if not cert:
        return CanaryVerificationVerdict.CERTIFICATE_NOT_FOUND, f"证书 {certificate_id} 不存在"

    recomputed_json = canonicalize_payload(cert.canonical_payload)
    recomputed_sha256 = compute_evidence_sha256(recomputed_json)

    if not hmac.compare_digest(recomputed_sha256, cert.evidence_sha256):
        return (
            CanaryVerificationVerdict.TAMPERED_INVALID,
            f"SHA-256 指纹不匹配！原始={cert.evidence_sha256}, 重算={recomputed_sha256}",
        )

    expected_signature = compute_hmac_signature(recomputed_sha256, secret_key=secret_key)
    if not hmac.compare_digest(expected_signature, cert.hmac_signature):
        return (
            CanaryVerificationVerdict.TAMPERED_INVALID,
            f"HMAC 签名校验失败！原始={cert.hmac_signature}, 重算={expected_signature}",
        )

    return CanaryVerificationVerdict.VALID, "证书合规完整，数据未发生任何篡改"
