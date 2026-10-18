"""容量基线推演结论与压测验收 64 位 SHA-256 存证证书器服务 (T4.2)

为全链路影子压测全流程产物（USL 容量拐点、过载熔断看门狗裁决、影子数据清理审计、生产强准入）提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, compact separators);
2. 64 字符十六进制 SHA-256 存证防伪指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发、存储检索与在线合规验签防篡改探针 (StressEvidenceCertificate: VALID | TAMPERED_INVALID)。
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

from app.services.capacity_knee_point_deductor import CapacityKneePointReport
from app.services.shadow_data_pollution_cleaner import ShadowDataCleanReport
from app.services.stress_safety_boundary_guard import StressSafetyAdmissionVerdict
from app.services.stress_safety_overload_guard import StressOverloadGuardVerdict


class StressArtifactType(str, enum.Enum):
    CAPACITY_KNEE_POINT_DEDUCTION = "CAPACITY_KNEE_POINT_DEDUCTION"  # USL 容量拐点与天花板推演
    STRESS_OVERLOAD_CIRCUIT_BREAK = "STRESS_OVERLOAD_CIRCUIT_BREAK"  # 生产击穿熔断断路看门狗裁决
    SHADOW_DATA_CLEAN_AUDIT = "SHADOW_DATA_CLEAN_AUDIT"  # 影子数据防污染与清理审计报告
    STRESS_SAFETY_ADMISSION_VERDICT = "STRESS_SAFETY_ADMISSION_VERDICT"  # 生产环境三要素强准入放行裁决


class StressVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未发生任何篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class StressEvidenceCertificate:
    certificate_id: str
    artifact_type: StressArtifactType
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


_STRESS_CERT_STORE: Dict[str, StressEvidenceCertificate] = {}
_DEFAULT_STRESS_SECRET = b"atp-v6-2-0-stress-testing-evidence-secret-2026"


def clear_stress_certificates() -> None:
    """清空压测存证证书内存库（测试隔离使用）"""
    _STRESS_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算规范化 JSON 数据的 64 位 SHA-256 哈希指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_hmac_signature(evidence_sha256: str, secret_key: bytes = _DEFAULT_STRESS_SECRET) -> str:
    """对 SHA-256 哈希指纹生成平台权威防伪 HMAC 签名"""
    return hmac.new(secret_key, evidence_sha256.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_stress_artifact(
    artifact_type: StressArtifactType,
    artifact_id: str,
    target_service: str,
    payload: Dict[str, Any],
    summary: Dict[str, Any],
    signer_identity: str = "ATP-STRESS-CONTROL-AUTHORITY-v6.2.0",
    secret_key: bytes = _DEFAULT_STRESS_SECRET,
) -> StressEvidenceCertificate:
    """通用全链路压测产物存证证书签发"""
    cert_id = f"cert_str_{uuid.uuid4().hex[:12]}"
    canonical_json = canonicalize_payload(payload)
    sha256_hash = compute_evidence_sha256(canonical_json)
    signature = compute_hmac_signature(sha256_hash, secret_key=secret_key)

    cert = StressEvidenceCertificate(
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
    _STRESS_CERT_STORE[cert_id] = cert
    return cert


def sign_capacity_knee_point_report(report: CapacityKneePointReport) -> StressEvidenceCertificate:
    """为 USL 容量拐点与天花板推演报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "report_id": report.report_id,
        "target_service": report.target_service,
        "gamma_efficiency": report.gamma_efficiency,
        "sigma_contention": report.sigma_contention,
        "kappa_coherency": report.kappa_coherency,
        "knee_point_vu": report.knee_point_vu,
        "knee_point_tps": report.knee_point_tps,
        "saturation_vu": report.saturation_vu,
        "peak_tps_ceiling": report.peak_tps_ceiling,
        "recommended_safe_concurrency": report.recommended_safe_concurrency,
        "r_squared_fit": report.r_squared_fit,
    }
    return sign_stress_artifact(
        artifact_type=StressArtifactType.CAPACITY_KNEE_POINT_DEDUCTION,
        artifact_id=report.report_id,
        target_service=report.target_service,
        payload=payload,
        summary=summary,
    )


def sign_stress_overload_guard_verdict(verdict: StressOverloadGuardVerdict) -> StressEvidenceCertificate:
    """为生产击穿熔断断路看门狗裁决签发存证证书"""
    payload = verdict.to_dict()
    summary = {
        "guard_verdict_id": verdict.guard_verdict_id,
        "target_service": verdict.target_service,
        "is_tripped": verdict.is_tripped,
        "action": verdict.action.value,
        "disabled_rules_count": verdict.disabled_rules_count,
        "tripped_reasons": verdict.tripped_reasons,
    }
    return sign_stress_artifact(
        artifact_type=StressArtifactType.STRESS_OVERLOAD_CIRCUIT_BREAK,
        artifact_id=verdict.guard_verdict_id,
        target_service=verdict.target_service,
        payload=payload,
        summary=summary,
    )


def sign_shadow_data_clean_report(report: ShadowDataCleanReport) -> StressEvidenceCertificate:
    """为影子数据防污染与清理审计报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "clean_job_id": report.clean_job_id,
        "target_service": report.target_service,
        "is_dry_run": report.is_dry_run,
        "cleaned_resources_count": report.cleaned_resources_count,
        "total_purged_records": report.total_purged_records,
        "reclaimed_space_mb": report.reclaimed_space_mb,
    }
    return sign_stress_artifact(
        artifact_type=StressArtifactType.SHADOW_DATA_CLEAN_AUDIT,
        artifact_id=report.clean_job_id,
        target_service=report.target_service,
        payload=payload,
        summary=summary,
    )


def sign_stress_safety_admission_verdict(verdict: StressSafetyAdmissionVerdict) -> StressEvidenceCertificate:
    """为生产全链路压测三要素强准入放行结论签发存证证书"""
    payload = verdict.to_dict()
    summary = {
        "verdict_id": verdict.verdict_id,
        "target_service": verdict.target_service,
        "environment": verdict.environment,
        "is_admitted": verdict.is_admitted,
        "verdict_code": verdict.verdict_code.value,
        "planned_peak_vu": verdict.planned_peak_vu,
        "reasons": verdict.reasons,
    }
    return sign_stress_artifact(
        artifact_type=StressArtifactType.STRESS_SAFETY_ADMISSION_VERDICT,
        artifact_id=verdict.verdict_id,
        target_service=verdict.target_service,
        payload=payload,
        summary=summary,
    )


def get_stress_certificate(certificate_id: str) -> Optional[StressEvidenceCertificate]:
    """根据证书 ID 查询压测存证记录"""
    return _STRESS_CERT_STORE.get(certificate_id)


def list_stress_certificates(target_service: Optional[str] = None) -> List[StressEvidenceCertificate]:
    """查询存证证书列表，支持微服务名称过滤"""
    certs = list(_STRESS_CERT_STORE.values())
    if target_service:
        certs = [c for c in certs if c.target_service == target_service]
    return sorted(certs, key=lambda c: c.issued_at, reverse=True)


def verify_stress_certificate(
    certificate_id: str,
    secret_key: bytes = _DEFAULT_STRESS_SECRET,
) -> Tuple[StressVerificationVerdict, Optional[str]]:
    """防篡改合规验签探针: 重新计算 Canonical JSON、SHA-256 与 HMAC-SHA256 签名并执行恒定时间比对"""
    cert = get_stress_certificate(certificate_id)
    if not cert:
        return StressVerificationVerdict.CERTIFICATE_NOT_FOUND, f"证书 {certificate_id} 不存在"

    recomputed_json = canonicalize_payload(cert.canonical_payload)
    recomputed_sha256 = compute_evidence_sha256(recomputed_json)

    if not hmac.compare_digest(recomputed_sha256, cert.evidence_sha256):
        return (
            StressVerificationVerdict.TAMPERED_INVALID,
            f"SHA-256 指纹不匹配！原始={cert.evidence_sha256}, 重算={recomputed_sha256}",
        )

    expected_signature = compute_hmac_signature(recomputed_sha256, secret_key=secret_key)
    if not hmac.compare_digest(expected_signature, cert.hmac_signature):
        return (
            StressVerificationVerdict.TAMPERED_INVALID,
            f"HMAC 签名校验失败！原始={cert.hmac_signature}, 重算={expected_signature}",
        )

    return StressVerificationVerdict.VALID, "证书合规完整，数据未发生任何篡改"
