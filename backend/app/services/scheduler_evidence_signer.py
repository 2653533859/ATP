"""调度决策与集群容量 64 位 SHA-256 存证签名服务 (T4.2)

为物理真机集群调度派发决策与容量水位快照提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, stripped spaces);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防篡改数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (SchedulerEvidenceCertificate: VALID | TAMPERED_INVALID)。
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

from app.services.fleet_concurrency_router import RoutingDecisionResult


class SchedulerArtifactType(str, enum.Enum):
    ROUTING_DECISION = "ROUTING_DECISION"  # 调度路由决策记录
    CAPACITY_SNAPSHOT = "CAPACITY_SNAPSHOT"  # 集群容量快照


class SchedulerVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class SchedulerEvidenceCertificate:
    certificate_id: str
    artifact_type: SchedulerArtifactType
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


_SCHEDULER_CERT_STORE: Dict[str, SchedulerEvidenceCertificate] = {}
_DEFAULT_SCHEDULER_SECRET = b"atp-v5-4-0-fleet-scheduler-evidence-secret-2026"


def clear_scheduler_certificates() -> None:
    """清空存证证书内存库（测试使用）"""
    _SCHEDULER_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算 64 字符十六进制 SHA-256 存证指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def sign_sha256_hash(sha256_hash: str, secret: bytes = _DEFAULT_SCHEDULER_SECRET) -> str:
    """对 64 位 SHA-256 哈希计算 HMAC-SHA256 防伪数字签名"""
    return hmac.new(secret, sha256_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_routing_decision_evidence(
    decision: RoutingDecisionResult,
    signer_identity: str = "ATP_FLEET_SCHEDULER_AUTHORITY_V5_4",
) -> SchedulerEvidenceCertificate:
    """为单次任务调度派发决策签发 64 位 SHA-256 存证证书"""
    cid = f"cert_route_{uuid.uuid4().hex[:12]}"

    candidates_summary = [
        {
            "device_id": c.device_id,
            "platform": c.platform,
            "eligible": c.eligible,
            "fitness": round(c.composite_fitness, 4),
        }
        for c in sorted(decision.candidate_evaluations, key=lambda x: x.device_id)
    ]

    canonical_data = {
        "artifact_id": decision.decision_id,
        "artifact_type": SchedulerArtifactType.ROUTING_DECISION.value,
        "task_id": decision.task_id,
        "target_platform": decision.target_platform,
        "status": decision.status.value,
        "selected_device_id": decision.selected_device_id or "",
        "fitness_score": round(decision.fitness_score, 4),
        "candidates": candidates_summary,
        "routing_reason": decision.routing_reason,
    }

    canon_str = canonicalize_payload(canonical_data)
    evidence_sha256 = compute_evidence_sha256(canon_str)
    signature = sign_sha256_hash(evidence_sha256)

    cert = SchedulerEvidenceCertificate(
        certificate_id=cid,
        artifact_type=SchedulerArtifactType.ROUTING_DECISION,
        artifact_id=decision.decision_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=evidence_sha256,
        hmac_signature=signature,
        canonical_payload=canonical_data,
        summary={
            "decision_id": decision.decision_id,
            "task_id": decision.task_id,
            "selected_device": decision.selected_device_id,
            "fitness_score": round(decision.fitness_score, 2),
            "status": decision.status.value,
        },
    )

    _SCHEDULER_CERT_STORE[cid] = cert
    return cert


def sign_capacity_snapshot_evidence(
    snapshot_id: str,
    capacity_data: Dict[str, Any],
    signer_identity: str = "ATP_CAPACITY_MONITOR_AUTHORITY_V5_4",
) -> SchedulerEvidenceCertificate:
    """为集群容量与算力快照签发 64 位 SHA-256 存证证书"""
    cid = f"cert_capsnap_{uuid.uuid4().hex[:12]}"

    canonical_data = {
        "artifact_id": snapshot_id,
        "artifact_type": SchedulerArtifactType.CAPACITY_SNAPSHOT.value,
        "total_devices": capacity_data.get("total_devices", 0),
        "healthy_count": capacity_data.get("healthy_count", 0),
        "total_capacity": capacity_data.get("total_capacity", 0),
        "used_concurrency": capacity_data.get("used_concurrency", 0),
        "available_capacity": capacity_data.get("available_capacity", 0),
        "cluster_averages": dict(sorted(capacity_data.get("cluster_averages", {}).items())),
    }

    canon_str = canonicalize_payload(canonical_data)
    evidence_sha256 = compute_evidence_sha256(canon_str)
    signature = sign_sha256_hash(evidence_sha256)

    cert = SchedulerEvidenceCertificate(
        certificate_id=cid,
        artifact_type=SchedulerArtifactType.CAPACITY_SNAPSHOT,
        artifact_id=snapshot_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=evidence_sha256,
        hmac_signature=signature,
        canonical_payload=canonical_data,
        summary={
            "snapshot_id": snapshot_id,
            "total_devices": capacity_data.get("total_devices", 0),
            "available_capacity": capacity_data.get("available_capacity", 0),
            "used_concurrency": capacity_data.get("used_concurrency", 0),
        },
    )

    _SCHEDULER_CERT_STORE[cid] = cert
    return cert


def verify_scheduler_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_SCHEDULER_SECRET,
) -> Tuple[SchedulerVerificationVerdict, str]:
    """在线核验证书 64 位 SHA-256 指纹未篡改与 HMAC 签名有效性"""
    cert = _SCHEDULER_CERT_STORE.get(certificate_id)
    if not cert:
        return SchedulerVerificationVerdict.CERTIFICATE_NOT_FOUND, f"存证证书 [{certificate_id}] 不存在"

    # 1. 重新从规范载荷计算 SHA-256
    recomputed_canon = canonicalize_payload(cert.canonical_payload)
    recomputed_sha256 = compute_evidence_sha256(recomputed_canon)

    if recomputed_sha256 != cert.evidence_sha256:
        return (
            SchedulerVerificationVerdict.TAMPERED_INVALID,
            f"存证指纹被篡改: 记录值={cert.evidence_sha256}, 重算值={recomputed_sha256}",
        )

    # 2. 重新验证 HMAC-SHA256 防伪数字签名
    expected_sig = sign_sha256_hash(recomputed_sha256, secret=secret)
    if not hmac.compare_digest(expected_sig, cert.hmac_signature):
        return (
            SchedulerVerificationVerdict.TAMPERED_INVALID,
            "平台 HMAC 防伪数字签名校验失败，可能被伪造或私钥不匹配",
        )

    return SchedulerVerificationVerdict.VALID, "调度存证证书签名合规，64 位 SHA-256 指纹完整无篡改"


def get_scheduler_certificate(certificate_id: str) -> Optional[SchedulerEvidenceCertificate]:
    """查询单张调度存证证书"""
    return _SCHEDULER_CERT_STORE.get(certificate_id)


def list_scheduler_certificates(limit: int = 50) -> List[Dict[str, Any]]:
    """查询近期颁发的调度存证证书列表"""
    certs = list(_SCHEDULER_CERT_STORE.values())
    certs.sort(key=lambda x: x.issued_at, reverse=True)
    return [c.to_dict() for c in certs[:limit]]
