"""流量回放与 Diff 报告 64 位 SHA-256 存证证书器服务 (T4.2)

为生产镜像流量记录、双端响应 Diff 报告与回放门禁裁决结果提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, stripped spaces);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (ReplayEvidenceCertificate: VALID | TAMPERED_INVALID)。
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


class ReplayArtifactType(str, enum.Enum):
    TRAFFIC_RECORD = "TRAFFIC_RECORD"  # 生产镜像流量录制记录
    DIFF_REPORT = "DIFF_REPORT"  # 双端响应体结构比对报告
    REPLAY_EVALUATION = "REPLAY_EVALUATION"  # 回放一致性综合裁决结果


class ReplayVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class ReplayEvidenceCertificate:
    certificate_id: str
    artifact_type: ReplayArtifactType
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


_REPLAY_CERT_STORE: Dict[str, ReplayEvidenceCertificate] = {}
_DEFAULT_REPLAY_SECRET = b"atp-v5-6-0-traffic-replay-evidence-secret-2026"


def clear_replay_certificates() -> None:
    """清空存证证书内存库（测试隔离使用）"""
    _REPLAY_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_str: str) -> str:
    """计算 64 字符十六进制 SHA-256 摘要哈希"""
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def sign_payload_hmac(canonical_str: str, secret: bytes = _DEFAULT_REPLAY_SECRET) -> str:
    """计算权威 HMAC-SHA256 防伪数字签名"""
    return hmac.new(secret, canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_traffic_record_certificate(
    record: Any,
    secret: bytes = _DEFAULT_REPLAY_SECRET,
) -> ReplayEvidenceCertificate:
    """为生产镜像流量记录签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_trf_{uuid.uuid4().hex[:10]}"
    payload_dict = record.to_dict() if hasattr(record, "to_dict") else dict(record)

    clean_payload = {
        "record_id": payload_dict.get("record_id", f"trf_{uuid.uuid4().hex[:8]}"),
        "trace_id": payload_dict.get("trace_id"),
        "method": payload_dict.get("method"),
        "path": payload_dict.get("path"),
        "status_code": payload_dict.get("status_code"),
        "is_sanitized": payload_dict.get("is_sanitized", False),
        "request_body": payload_dict.get("request_body"),
        "response_body": payload_dict.get("response_body"),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "record_id": clean_payload.get("record_id"),
        "method": clean_payload.get("method"),
        "path": clean_payload.get("path"),
        "status_code": clean_payload.get("status_code"),
        "is_sanitized": clean_payload.get("is_sanitized"),
    }

    cert = ReplayEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=ReplayArtifactType.TRAFFIC_RECORD,
        artifact_id=str(clean_payload["record_id"]),
        signer_identity="ATP_TRAFFIC_REPLAY_SIGNER_V5_6",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _REPLAY_CERT_STORE[cert_id] = cert
    return cert


def sign_diff_report_certificate(
    diff_report: Any,
    secret: bytes = _DEFAULT_REPLAY_SECRET,
) -> ReplayEvidenceCertificate:
    """为双端响应结构比对报告签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_diff_{uuid.uuid4().hex[:10]}"
    payload_dict = diff_report.to_dict() if hasattr(diff_report, "to_dict") else dict(diff_report)

    clean_payload = {
        "report_id": payload_dict.get("report_id", f"diff_{uuid.uuid4().hex[:8]}"),
        "record_id": payload_dict.get("record_id"),
        "baseline_status_code": payload_dict.get("baseline_status_code"),
        "replayed_status_code": payload_dict.get("replayed_status_code"),
        "is_identical": payload_dict.get("is_identical"),
        "has_critical_breaking": payload_dict.get("has_critical_breaking"),
        "diff_count": payload_dict.get("diff_count", 0),
        "diff_summary": payload_dict.get("diff_summary", {}),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "report_id": clean_payload.get("report_id"),
        "record_id": clean_payload.get("record_id"),
        "is_identical": clean_payload.get("is_identical"),
        "diff_count": clean_payload.get("diff_count"),
        "has_critical_breaking": clean_payload.get("has_critical_breaking"),
    }

    cert = ReplayEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=ReplayArtifactType.DIFF_REPORT,
        artifact_id=str(clean_payload["report_id"]),
        signer_identity="ATP_TRAFFIC_REPLAY_SIGNER_V5_6",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _REPLAY_CERT_STORE[cert_id] = cert
    return cert


def sign_replay_evaluation_certificate(
    evaluation: Any,
    secret: bytes = _DEFAULT_REPLAY_SECRET,
) -> ReplayEvidenceCertificate:
    """为回放一致性综合裁决结果签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_eval_{uuid.uuid4().hex[:10]}"
    payload_dict = evaluation.to_dict() if hasattr(evaluation, "to_dict") else dict(evaluation)

    clean_payload = {
        "evaluation_id": payload_dict.get("evaluation_id", f"eval_{uuid.uuid4().hex[:8]}"),
        "record_id": payload_dict.get("record_id"),
        "consistency_score": payload_dict.get("consistency_score"),
        "impact_level": payload_dict.get("impact_level"),
        "verdict": payload_dict.get("verdict"),
        "is_deployable": payload_dict.get("is_deployable"),
        "effective_diff_count": payload_dict.get("effective_diff_count", 0),
        "suppressed_noise_count": payload_dict.get("suppressed_noise_count", 0),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "evaluation_id": clean_payload.get("evaluation_id"),
        "record_id": clean_payload.get("record_id"),
        "consistency_score": clean_payload.get("consistency_score"),
        "verdict": clean_payload.get("verdict"),
        "is_deployable": clean_payload.get("is_deployable"),
    }

    cert = ReplayEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=ReplayArtifactType.REPLAY_EVALUATION,
        artifact_id=str(clean_payload["evaluation_id"]),
        signer_identity="ATP_TRAFFIC_REPLAY_SIGNER_V5_6",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _REPLAY_CERT_STORE[cert_id] = cert
    return cert


def verify_replay_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_REPLAY_SECRET,
) -> Tuple[ReplayVerificationVerdict, str]:
    """在线验证存证证书的 SHA-256 指纹一致性与 HMAC-SHA256 平台防伪签名"""
    cert = _REPLAY_CERT_STORE.get(certificate_id)
    if not cert:
        return ReplayVerificationVerdict.CERTIFICATE_NOT_FOUND, f"未找到存证证书 [{certificate_id}]"

    canonical_str = canonicalize_payload(cert.canonical_payload)
    recalculated_sha256 = compute_evidence_sha256(canonical_str)

    if not hmac.compare_digest(cert.evidence_sha256, recalculated_sha256):
        return (
            ReplayVerificationVerdict.TAMPERED_INVALID,
            f"SHA-256 指纹不匹配！原指纹: {cert.evidence_sha256}，重算指纹: {recalculated_sha256}",
        )

    expected_sig = sign_payload_hmac(canonical_str, secret)
    if not hmac.compare_digest(cert.hmac_signature, expected_sig):
        return ReplayVerificationVerdict.TAMPERED_INVALID, "HMAC-SHA256 平台防伪数字签名无效，疑似篡改！"

    return ReplayVerificationVerdict.VALID, f"存证证书 [{certificate_id}] 密码学验签通过 (SHA-256 / HMAC-SHA256 一致)"


def get_replay_certificate(certificate_id: str) -> Optional[ReplayEvidenceCertificate]:
    """获取单张存证证书"""
    return _REPLAY_CERT_STORE.get(certificate_id)


def list_replay_certificates(
    artifact_type: Optional[ReplayArtifactType] = None,
    limit: int = 50,
) -> List[ReplayEvidenceCertificate]:
    """查询存证证书流水列表"""
    items = list(_REPLAY_CERT_STORE.values())
    if artifact_type:
        items = [i for i in items if i.artifact_type == artifact_type]

    items.sort(key=lambda x: x.issued_at, reverse=True)
    return items[:limit]
