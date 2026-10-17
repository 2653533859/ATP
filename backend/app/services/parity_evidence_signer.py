"""双端一致性与跨端迁移证据 64 位 SHA-256 存证签名服务 (T4.2)

为跨端迁移用例拓扑与双端功能一致性审计报告提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防篡改数字签名 (HMAC-SHA256);
4. 证书签发与在线验签防篡改探针 (ParityEvidenceCertificate: VALID | TAMPERED_INVALID)。
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

from app.services.cross_platform_action_mapper import ActionMappingResult
from app.services.parity_scoring_engine import ParityAuditReport


class ParityArtifactType(str, enum.Enum):
    CASE_MIGRATION = "CASE_MIGRATION"  # 跨端用例转译产物
    PARITY_REPORT = "PARITY_REPORT"  # 双端一致性审计报告


class ParityVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class ParityEvidenceCertificate:
    certificate_id: str
    artifact_type: ParityArtifactType
    artifact_id: str
    signer_identity: str
    algorithm: str  # SHA-256/HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256 摘要
    hmac_signature: str
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_PARITY_CERT_STORE: Dict[str, ParityEvidenceCertificate] = {}
_DEFAULT_PARITY_SECRET = b"atp-v5-3-0-cross-platform-parity-evidence-secret-2026"


def clear_parity_certificates() -> None:
    """清空存证证书内存库（测试使用）"""
    _PARITY_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算 64 字符十六进制 SHA-256 存证指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def sign_sha256_hash(sha256_hash: str, secret: bytes = _DEFAULT_PARITY_SECRET) -> str:
    """对 64 位 SHA-256 哈希计算 HMAC-SHA256 防伪数字签名"""
    return hmac.new(secret, sha256_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_case_migration_evidence(
    mapping_result: ActionMappingResult,
    signer_identity: str = "ATP_CROSS_PLATFORM_AUTHORITY_V5_3",
) -> ParityEvidenceCertificate:
    """为跨端用例转译映射产物签发 64 位 SHA-256 存证证书"""
    cid = f"cert_mig_{uuid.uuid4().hex[:12]}"

    steps_summary = [
        {
            "step_id": s.step_id,
            "action_type": s.action_type.value,
            "source_platform": s.source_platform.value,
            "target_platform": s.target_platform.value,
            "source_locator": s.source_locator.to_dict() if s.source_locator else None,
            "target_locator": s.target_locator.to_dict() if s.target_locator else None,
            "confidence": round(s.confidence, 4),
        }
        for s in sorted(mapping_result.mapped_steps, key=lambda x: x.step_id)
    ]

    canonical_data = {
        "artifact_id": mapping_result.mapping_id,
        "artifact_type": ParityArtifactType.CASE_MIGRATION.value,
        "source_platform": mapping_result.source_platform.value,
        "target_platform": mapping_result.target_platform.value,
        "total_steps": mapping_result.total_steps,
        "mapped_steps_count": mapping_result.mapped_steps_count,
        "average_confidence": round(mapping_result.average_confidence, 4),
        "steps": steps_summary,
    }

    canon_str = canonicalize_payload(canonical_data)
    evidence_sha256 = compute_evidence_sha256(canon_str)
    signature = sign_sha256_hash(evidence_sha256)

    cert = ParityEvidenceCertificate(
        certificate_id=cid,
        artifact_type=ParityArtifactType.CASE_MIGRATION,
        artifact_id=mapping_result.mapping_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=evidence_sha256,
        hmac_signature=signature,
        canonical_payload=canonical_data,
        summary={
            "mapping_id": mapping_result.mapping_id,
            "transfer": f"{mapping_result.source_platform.value} -> {mapping_result.target_platform.value}",
            "steps_count": mapping_result.mapped_steps_count,
            "average_confidence": round(mapping_result.average_confidence, 4),
        },
    )

    _PARITY_CERT_STORE[cid] = cert
    return cert


def sign_parity_report_evidence(
    report: ParityAuditReport,
    signer_identity: str = "ATP_PARITY_AUDIT_AUTHORITY_V5_3",
) -> ParityEvidenceCertificate:
    """为双端功能一致性审计报表签发 64 位 SHA-256 存证证书"""
    cid = f"cert_parrep_{uuid.uuid4().hex[:12]}"

    canonical_data = {
        "artifact_id": report.report_id,
        "artifact_type": ParityArtifactType.PARITY_REPORT.value,
        "screen_name": report.screen_name,
        "source_platform": report.source_platform,
        "target_platform": report.target_platform,
        "composite_score": round(report.composite_score, 4),
        "grade": report.grade.value,
        "verdict": report.verdict.value,
        "matrix_summary": dict(sorted(report.matrix_summary.items())),
        "discrepancy_summary": dict(sorted(report.discrepancy_summary.items())),
    }

    canon_str = canonicalize_payload(canonical_data)
    evidence_sha256 = compute_evidence_sha256(canon_str)
    signature = sign_sha256_hash(evidence_sha256)

    cert = ParityEvidenceCertificate(
        certificate_id=cid,
        artifact_type=ParityArtifactType.PARITY_REPORT,
        artifact_id=report.report_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=evidence_sha256,
        hmac_signature=signature,
        canonical_payload=canonical_data,
        summary={
            "screen_name": report.screen_name,
            "transfer": f"{report.source_platform} -> {report.target_platform}",
            "composite_score": round(report.composite_score, 2),
            "grade": report.grade.value,
            "verdict": report.verdict.value,
        },
    )

    _PARITY_CERT_STORE[cid] = cert
    return cert


def verify_parity_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_PARITY_SECRET,
) -> Tuple[ParityVerificationVerdict, str]:
    """在线核验证书 64 位 SHA-256 指纹未篡改与 HMAC 签名有效性"""
    cert = _PARITY_CERT_STORE.get(certificate_id)
    if not cert:
        return ParityVerificationVerdict.CERTIFICATE_NOT_FOUND, f"存证证书 [{certificate_id}] 不存在"

    # 1. 重新从规范载荷计算 SHA-256
    recomputed_canon = canonicalize_payload(cert.canonical_payload)
    recomputed_sha256 = compute_evidence_sha256(recomputed_canon)

    if recomputed_sha256 != cert.evidence_sha256:
        return (
            ParityVerificationVerdict.TAMPERED_INVALID,
            f"存证指纹被篡改: 记录值={cert.evidence_sha256}, 重算值={recomputed_sha256}",
        )

    # 2. 重新验证 HMAC-SHA256 防伪数字签名
    expected_sig = sign_sha256_hash(recomputed_sha256, secret=secret)
    if not hmac.compare_digest(expected_sig, cert.hmac_signature):
        return (
            ParityVerificationVerdict.TAMPERED_INVALID,
            "平台 HMAC 防伪数字签名校验失败，可能被伪造或密钥不匹配",
        )

    return ParityVerificationVerdict.VALID, "双端一致性存证证书签名合规，64 位 SHA-256 指纹完整无篡改"


def get_parity_certificate(certificate_id: str) -> Optional[ParityEvidenceCertificate]:
    """查询单张存证证书"""
    return _PARITY_CERT_STORE.get(certificate_id)


def list_parity_certificates(limit: int = 50) -> List[Dict[str, Any]]:
    """查询近期颁发的一致性存证证书列表"""
    certs = list(_PARITY_CERT_STORE.values())
    certs.sort(key=lambda x: x.issued_at, reverse=True)
    return [c.to_dict() for c in certs[:limit]]
