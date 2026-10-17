"""自愈补丁与断言演进 64 位 SHA-256 存证证书器服务 (T4.2)

为定位器自愈补丁与语义断言演进快照提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, stripped spaces);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (HealingEvidenceCertificate: VALID | TAMPERED_INVALID)。
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


class HealingArtifactType(str, enum.Enum):
    LOCATOR_PATCH = "LOCATOR_PATCH"  # 定位器自愈补丁记录
    ASSERTION_EVOLUTION = "ASSERTION_EVOLUTION"  # 语义断言演进快照


class HealingVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class HealingEvidenceCertificate:
    certificate_id: str
    artifact_type: HealingArtifactType
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


_HEALING_CERT_STORE: Dict[str, HealingEvidenceCertificate] = {}
_DEFAULT_HEALING_SECRET = b"atp-v5-5-0-self-healing-evidence-secret-2026"


def clear_healing_certificates() -> None:
    """清空存证证书内存库（测试隔离）"""
    _HEALING_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_str: str) -> str:
    """计算 64 字符十六进制 SHA-256 摘要哈希"""
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def sign_payload_hmac(canonical_str: str, secret: bytes = _DEFAULT_HEALING_SECRET) -> str:
    """计算权威 HMAC-SHA256 防伪数字签名"""
    return hmac.new(secret, canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_healing_patch_certificate(
    patch_record: Any,
    secret: bytes = _DEFAULT_HEALING_SECRET,
) -> HealingEvidenceCertificate:
    """为定位器自愈补丁签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_patch_{uuid.uuid4().hex[:10]}"

    payload_dict = patch_record.to_dict() if hasattr(patch_record, "to_dict") else dict(patch_record)

    clean_payload = {
        "patch_id": payload_dict.get("patch_id", f"patch_{uuid.uuid4().hex[:8]}"),
        "case_id": payload_dict.get("case_id"),
        "step_id": payload_dict.get("step_id"),
        "status": payload_dict.get("status"),
        "confidence": payload_dict.get("confidence"),
        "broken_context": payload_dict.get("broken_context"),
        "best_candidate": payload_dict.get("best_candidate"),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "step_id": clean_payload.get("step_id"),
        "case_id": clean_payload.get("case_id"),
        "status": clean_payload.get("status"),
        "confidence": clean_payload.get("confidence"),
        "winning_strategy": (clean_payload.get("best_candidate") or {}).get("strategy_tier", "TIER_1"),
    }

    cert = HealingEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=HealingArtifactType.LOCATOR_PATCH,
        artifact_id=str(clean_payload["patch_id"]),
        signer_identity="ATP_SELF_HEALING_SIGNER_V5_5",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _HEALING_CERT_STORE[cert_id] = cert
    return cert


def sign_assertion_evolution_certificate(
    snapshot: Any,
    secret: bytes = _DEFAULT_HEALING_SECRET,
) -> HealingEvidenceCertificate:
    """为断言演进快照签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_evo_{uuid.uuid4().hex[:10]}"

    payload_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)

    clean_payload = {
        "version_id": payload_dict.get("version_id", f"ver_{uuid.uuid4().hex[:8]}"),
        "case_id": payload_dict.get("case_id"),
        "step_id": payload_dict.get("step_id"),
        "original_assertion": payload_dict.get("original_assertion"),
        "current_assertion": payload_dict.get("current_assertion"),
        "confidence_score": payload_dict.get("confidence_score"),
        "risk_level": payload_dict.get("risk_level"),
        "status": payload_dict.get("status"),
        "applied_drift_ids": payload_dict.get("applied_drift_ids", []),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "version_id": clean_payload.get("version_id"),
        "case_id": clean_payload.get("case_id"),
        "step_id": clean_payload.get("step_id"),
        "confidence_score": clean_payload.get("confidence_score"),
        "risk_level": clean_payload.get("risk_level"),
        "status": clean_payload.get("status"),
    }

    cert = HealingEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=HealingArtifactType.ASSERTION_EVOLUTION,
        artifact_id=str(clean_payload["version_id"]),
        signer_identity="ATP_SELF_HEALING_SIGNER_V5_5",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _HEALING_CERT_STORE[cert_id] = cert
    return cert


def verify_healing_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_HEALING_SECRET,
) -> Tuple[HealingVerificationVerdict, str]:
    """验证存证证书的 SHA-256 指纹一致性与 HMAC-SHA256 平台防伪签名"""
    cert = _HEALING_CERT_STORE.get(certificate_id)
    if not cert:
        return HealingVerificationVerdict.CERTIFICATE_NOT_FOUND, f"未找到存证证书 [{certificate_id}]"

    canonical_str = canonicalize_payload(cert.canonical_payload)
    recalculated_sha256 = compute_evidence_sha256(canonical_str)

    if not hmac.compare_digest(cert.evidence_sha256, recalculated_sha256):
        return (
            HealingVerificationVerdict.TAMPERED_INVALID,
            f"SHA-256 指纹不匹配！原指纹: {cert.evidence_sha256}，重算指纹: {recalculated_sha256}",
        )

    expected_sig = sign_payload_hmac(canonical_str, secret)
    if not hmac.compare_digest(cert.hmac_signature, expected_sig):
        return HealingVerificationVerdict.TAMPERED_INVALID, "HMAC-SHA256 平台防伪数字签名无效，疑似篡改！"

    return HealingVerificationVerdict.VALID, f"存证证书 [{certificate_id}] 密码学验签通过 (SHA-256 / HMAC-SHA256 一致)"


def get_healing_certificate(certificate_id: str) -> Optional[HealingEvidenceCertificate]:
    """获取单张存证证书"""
    return _HEALING_CERT_STORE.get(certificate_id)


def list_healing_certificates(
    artifact_type: Optional[HealingArtifactType] = None,
    limit: int = 50,
) -> List[HealingEvidenceCertificate]:
    """查询存证证书流水列表"""
    items = list(_HEALING_CERT_STORE.values())
    if artifact_type:
        items = [i for i in items if i.artifact_type == artifact_type]

    items.sort(key=lambda x: x.issued_at, reverse=True)
    return items[:limit]
