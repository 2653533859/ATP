"""追踪审计凭据 64 位 SHA-256 防篡改存证器服务 (T4.2)

为全链路微服务 Span 与测试用例步骤执行链路生成高保真防篡改凭据:
1. 规范化 JSON 序列化 (Canonical JSON);
2. 64 位十六进制 SHA-256 签名与 HMAC-SHA256 摘要指纹;
3. 存证凭据证书生成 (Evidence Certificate) 与防篡改校验器;
4. 任何对 Span 耗时、状态码、属性字典的篡改均会触发验签失败 (TAMPER_DETECTED)。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvidenceCertificate:
    trace_id: str
    run_id: str
    signer: str
    algorithm: str  # SHA-256
    spans_count: int
    services_involved: List[str]
    evidence_sha256: str
    hmac_signature: str
    canonical_payload_digest: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "signer": self.signer,
            "algorithm": self.algorithm,
            "spans_count": self.spans_count,
            "services_involved": self.services_involved,
            "evidence_sha256": self.evidence_sha256,
            "hmac_signature": self.hmac_signature,
            "canonical_payload_digest": self.canonical_payload_digest,
            "created_at": self.created_at,
        }


# 全局轻量级防篡改存证库
_EVIDENCE_STORE: Dict[str, TraceEvidenceCertificate] = {}

# 平台默认 HMAC 签名密钥 (支持环境覆盖)
_DEFAULT_HMAC_SECRET = b"atp-observability-trace-audit-secret-2026"


def clear_evidence_store() -> None:
    _EVIDENCE_STORE.clear()


def list_evidence_certificates(limit: int = 50) -> List[Dict[str, Any]]:
    return [c.to_dict() for c in list(_EVIDENCE_STORE.values())[-limit:]]


def get_evidence_certificate(trace_id: str) -> Optional[Dict[str, Any]]:
    cert = _EVIDENCE_STORE.get(trace_id)
    return cert.to_dict() if cert else None


def canonical_json_bytes(data: Any) -> bytes:
    """生成字典序规范化紧凑 JSON 字节流"""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_trace_evidence(
    trace_id: str,
    run_id: str,
    spans: List[Dict[str, Any]],
    secret_key: bytes | None = None,
    signer: str = "atp-trace-auditor-v4.9",
) -> TraceEvidenceCertificate:
    """为全链路 Span 列表生成规范化 SHA-256 摘要与防篡改存证证书"""
    secret = secret_key or _DEFAULT_HMAC_SECRET

    # 1. 提取微服务列表与核心字段进行规范化精简
    services: set[str] = set()
    sanitized_spans_summary: List[Dict[str, Any]] = []

    for s in spans:
        svc = str(s.get("service_name", "unknown"))
        services.add(svc)
        sanitized_spans_summary.append(
            {
                "span_id": str(s.get("span_id", "")),
                "parent_span_id": str(s.get("parent_span_id") or ""),
                "service_name": svc,
                "name": str(s.get("name", "")),
                "duration_ms": float(s.get("duration_ms", 0.0)),
                "status": s.get("status", {}),
                "attributes": s.get("attributes", {}),
            }
        )

    # 按 span_id 排序确保确定性
    sanitized_spans_summary.sort(key=lambda x: x["span_id"])

    evidence_payload = {
        "trace_id": trace_id,
        "run_id": run_id,
        "spans": sanitized_spans_summary,
    }

    # 2. 计算规范化 JSON 与 SHA-256 指纹
    raw_bytes = canonical_json_bytes(evidence_payload)
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    # 3. 计算防伪造 HMAC 签名
    hmac_sig = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    cert = TraceEvidenceCertificate(
        trace_id=trace_id,
        run_id=run_id,
        signer=signer,
        algorithm="SHA-256",
        spans_count=len(spans),
        services_involved=sorted(list(services)),
        evidence_sha256=sha256_hash,
        hmac_signature=hmac_sig,
        canonical_payload_digest=f"size={len(raw_bytes)} bytes",
    )
    _EVIDENCE_STORE[trace_id] = cert
    return cert


def verify_trace_evidence(
    certificate: Dict[str, Any],
    spans: List[Dict[str, Any]],
    secret_key: bytes | None = None,
) -> tuple[bool, str]:
    """验证目标 Span 链路是否与存证证书完全吻合，检测是否存在数据篡改

    返回: (is_valid: bool, verification_message: str)
    """
    secret = secret_key or _DEFAULT_HMAC_SECRET

    trace_id = str(certificate.get("trace_id", ""))
    run_id = str(certificate.get("run_id", ""))
    expected_sha256 = str(certificate.get("evidence_sha256", ""))
    expected_hmac = str(certificate.get("hmac_signature", ""))

    # 重构摘要
    sanitized_spans_summary: List[Dict[str, Any]] = []
    for s in spans:
        sanitized_spans_summary.append(
            {
                "span_id": str(s.get("span_id", "")),
                "parent_span_id": str(s.get("parent_span_id") or ""),
                "service_name": str(s.get("service_name", "unknown")),
                "name": str(s.get("name", "")),
                "duration_ms": float(s.get("duration_ms", 0.0)),
                "status": s.get("status", {}),
                "attributes": s.get("attributes", {}),
            }
        )
    sanitized_spans_summary.sort(key=lambda x: x["span_id"])

    evidence_payload = {
        "trace_id": trace_id,
        "run_id": run_id,
        "spans": sanitized_spans_summary,
    }

    raw_bytes = canonical_json_bytes(evidence_payload)
    computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    computed_hmac = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    if computed_sha256 != expected_sha256:
        return False, f"TAMPERED_HASH_MISMATCH: 计算摘要 [{computed_sha256}] 与证书签名 [{expected_sha256}] 不符"

    if computed_hmac != expected_hmac:
        return False, f"TAMPERED_HMAC_MISMATCH: HMAC 鉴权防伪签名不匹配"

    return True, "EVIDENCE_VERIFIED: 链路指纹与 64 位 SHA-256 存证证书完全吻合，未检测到任何数据篡改"
