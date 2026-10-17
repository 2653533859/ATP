"""增量用例推荐与拓扑调度 64 位 SHA-256 存证证书器服务 (T4.2)

为精准回归推荐结果、用例 DAG 图谱与波次执行调度计划提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, stripped spaces);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (PrecisionEvidenceCertificate: VALID | TAMPERED_INVALID)。
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


class PrecisionArtifactType(str, enum.Enum):
    PRECISION_RECOMMENDATION = "PRECISION_RECOMMENDATION"  # 增量精准用例推荐结果
    DAG_TOPOLOGY = "DAG_TOPOLOGY"  # 用例依赖 DAG 拓扑图谱
    WAVE_EXECUTION_PLAN = "WAVE_EXECUTION_PLAN"  # 并发执行波次调度计划


class PrecisionVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class PrecisionEvidenceCertificate:
    certificate_id: str
    artifact_type: PrecisionArtifactType
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


_PRECISION_CERT_STORE: Dict[str, PrecisionEvidenceCertificate] = {}
_DEFAULT_PRECISION_SECRET = b"atp-v5-7-0-precision-regression-evidence-secret-2026"


def clear_precision_certificates() -> None:
    """清空存证证书内存库（测试隔离使用）"""
    _PRECISION_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_str: str) -> str:
    """计算 64 字符十六进制 SHA-256 摘要哈希"""
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def sign_payload_hmac(canonical_str: str, secret: bytes = _DEFAULT_PRECISION_SECRET) -> str:
    """计算权威 HMAC-SHA256 防伪数字签名"""
    return hmac.new(secret, canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_precision_recommendation_certificate(
    recommendation: Any,
    secret: bytes = _DEFAULT_PRECISION_SECRET,
) -> PrecisionEvidenceCertificate:
    """为增量精准推荐结果签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_prec_{uuid.uuid4().hex[:10]}"
    payload_dict = recommendation.to_dict() if hasattr(recommendation, "to_dict") else dict(recommendation)

    clean_payload = {
        "analysis_id": payload_dict.get("analysis_id", f"prec_{uuid.uuid4().hex[:8]}"),
        "changed_symbols": payload_dict.get("changed_symbols", []),
        "impacted_endpoints": payload_dict.get("impacted_endpoints", []),
        "impacted_cases_count": payload_dict.get("impacted_cases_count", 0),
        "total_cases_in_suite": payload_dict.get("total_cases_in_suite", 0),
        "regression_reduction_ratio": payload_dict.get("regression_reduction_ratio", 0.0),
        "estimated_time_saved_seconds": payload_dict.get("estimated_time_saved_seconds", 0.0),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "analysis_id": clean_payload["analysis_id"],
        "changed_symbols_count": len(clean_payload["changed_symbols"]),
        "impacted_cases_count": clean_payload["impacted_cases_count"],
        "reduction_ratio": clean_payload["regression_reduction_ratio"],
        "time_saved_seconds": clean_payload["estimated_time_saved_seconds"],
    }

    cert = PrecisionEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=PrecisionArtifactType.PRECISION_RECOMMENDATION,
        artifact_id=str(clean_payload["analysis_id"]),
        signer_identity="ATP_PRECISION_REGRESSION_SIGNER_V5_7",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _PRECISION_CERT_STORE[cert_id] = cert
    return cert


def sign_dag_topology_certificate(
    dag: Any,
    secret: bytes = _DEFAULT_PRECISION_SECRET,
) -> PrecisionEvidenceCertificate:
    """为用例依赖 DAG 图谱签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_dag_{uuid.uuid4().hex[:10]}"
    payload_dict = dag.to_dict() if hasattr(dag, "to_dict") else dict(dag)

    clean_payload = {
        "dag_id": payload_dict.get("dag_id", f"dag_{uuid.uuid4().hex[:8]}"),
        "is_valid_dag": payload_dict.get("is_valid_dag", True),
        "nodes_count": payload_dict.get("nodes_count", 0),
        "edges_count": payload_dict.get("edges_count", 0),
        "cycles_count": len(payload_dict.get("cycles", [])),
        "root_case_ids": payload_dict.get("root_case_ids", []),
        "leaf_case_ids": payload_dict.get("leaf_case_ids", []),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "dag_id": clean_payload["dag_id"],
        "is_valid_dag": clean_payload["is_valid_dag"],
        "nodes_count": clean_payload["nodes_count"],
        "edges_count": clean_payload["edges_count"],
    }

    cert = PrecisionEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=PrecisionArtifactType.DAG_TOPOLOGY,
        artifact_id=str(clean_payload["dag_id"]),
        signer_identity="ATP_PRECISION_REGRESSION_SIGNER_V5_7",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _PRECISION_CERT_STORE[cert_id] = cert
    return cert


def sign_wave_plan_certificate(
    plan: Any,
    secret: bytes = _DEFAULT_PRECISION_SECRET,
) -> PrecisionEvidenceCertificate:
    """为并发执行波次调度计划签发不可篡改 SHA-256 存证证书"""
    cert_id = f"cert_wave_{uuid.uuid4().hex[:10]}"
    payload_dict = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)

    clean_payload = {
        "plan_id": payload_dict.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}"),
        "dag_id": payload_dict.get("dag_id"),
        "total_waves_count": payload_dict.get("total_waves_count", 0),
        "total_cases_count": payload_dict.get("total_cases_count", 0),
        "critical_path_duration_seconds": payload_dict.get("critical_path_duration_seconds", 0.0),
        "sequential_duration_seconds": payload_dict.get("sequential_duration_seconds", 0.0),
        "concurrency_acceleration_ratio": payload_dict.get("concurrency_acceleration_ratio", 1.0),
    }

    canonical_str = canonicalize_payload(clean_payload)
    sha256_hash = compute_evidence_sha256(canonical_str)
    sig = sign_payload_hmac(canonical_str, secret)

    summary = {
        "plan_id": clean_payload["plan_id"],
        "total_waves_count": clean_payload["total_waves_count"],
        "acceleration_ratio": clean_payload["concurrency_acceleration_ratio"],
    }

    cert = PrecisionEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=PrecisionArtifactType.WAVE_EXECUTION_PLAN,
        artifact_id=str(clean_payload["plan_id"]),
        signer_identity="ATP_PRECISION_REGRESSION_SIGNER_V5_7",
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=sig,
        canonical_payload=clean_payload,
        summary=summary,
    )

    _PRECISION_CERT_STORE[cert_id] = cert
    return cert


def verify_precision_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_PRECISION_SECRET,
) -> Tuple[PrecisionVerificationVerdict, str]:
    """在线验证存证证书的 SHA-256 指纹一致性与 HMAC-SHA256 平台防伪签名"""
    cert = _PRECISION_CERT_STORE.get(certificate_id)
    if not cert:
        return PrecisionVerificationVerdict.CERTIFICATE_NOT_FOUND, f"未找到存证证书 [{certificate_id}]"

    canonical_str = canonicalize_payload(cert.canonical_payload)
    recalculated_sha256 = compute_evidence_sha256(canonical_str)

    if not hmac.compare_digest(cert.evidence_sha256, recalculated_sha256):
        return (
            PrecisionVerificationVerdict.TAMPERED_INVALID,
            f"SHA-256 指纹不匹配！原指纹: {cert.evidence_sha256}，重算指纹: {recalculated_sha256}",
        )

    expected_sig = sign_payload_hmac(canonical_str, secret)
    if not hmac.compare_digest(cert.hmac_signature, expected_sig):
        return PrecisionVerificationVerdict.TAMPERED_INVALID, "HMAC-SHA256 平台防伪数字签名无效，疑似篡改！"

    return (
        PrecisionVerificationVerdict.VALID,
        f"存证证书 [{certificate_id}] 密码学验签通过 (SHA-256 / HMAC-SHA256 一致)",
    )


def get_precision_certificate(certificate_id: str) -> Optional[PrecisionEvidenceCertificate]:
    """获取单张存证证书"""
    return _PRECISION_CERT_STORE.get(certificate_id)


def list_precision_certificates(
    artifact_type: Optional[PrecisionArtifactType] = None,
    limit: int = 50,
) -> List[PrecisionEvidenceCertificate]:
    """查询存证证书流水列表"""
    items = list(_PRECISION_CERT_STORE.values())
    if artifact_type:
        items = [i for i in items if i.artifact_type == artifact_type]

    items.sort(key=lambda x: x.issued_at, reverse=True)
    return items[:limit]
