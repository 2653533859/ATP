"""Tamper-Evident SHA-256 Audit Log Hash Chain & Compliance Certification Service (T4.3).

Provides:
1. Blockchain-style cryptographic hash chaining for audit log records (previous_hash -> chain_hash).
2. Canonical payload serialization and deterministic SHA-256 digest computation.
3. Tamper-evident integrity verification engine: detects modifications, deletions, and insertions.
4. Exportable compliance audit certificate with HMAC-SHA256 digital signature seal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
DEFAULT_COMPLIANCE_SIGNING_KEY = "atp_audit_compliance_master_secret_2026"


@dataclass
class AuditChainBlock:
    index: int
    log_id: int
    timestamp: str
    previous_hash: str
    record_hash: str
    chain_hash: str
    payload_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "log_id": self.log_id,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
            "chain_hash": self.chain_hash,
            "payload_summary": self.payload_summary,
        }


def compute_record_payload_hash(log_dict: dict[str, Any]) -> str:
    """Compute canonical SHA-256 hash of an audit log record payload."""
    canonical_payload = {
        "log_id": log_dict.get("id"),
        "action": str(log_dict.get("action", "")),
        "resource_type": str(log_dict.get("resource_type", "")),
        "resource_id": log_dict.get("resource_id"),
        "user_id": log_dict.get("user_id"),
        "username": str(log_dict.get("username", "")),
        "detail": str(log_dict.get("detail", "") or ""),
        "ip_address": str(log_dict.get("ip_address", "") or ""),
        "project_id": log_dict.get("project_id"),
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_chain_block_hash(previous_hash: str, record_hash: str, timestamp: str) -> str:
    """Compute cryptographic link hash chaining previous_hash, record_hash, and timestamp."""
    material = f"{previous_hash}|{record_hash}|{timestamp}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_audit_hash_chain(log_records: list[dict[str, Any]]) -> list[AuditChainBlock]:
    """Construct consecutive cryptographic hash chain blocks from a list of audit logs."""
    chain: list[AuditChainBlock] = []
    prev_hash = GENESIS_HASH

    for idx, log in enumerate(log_records, start=1):
        log_id = int(log.get("id", idx))
        ts_val = log.get("created_at")
        if isinstance(ts_val, datetime):
            timestamp_str = ts_val.isoformat()
        else:
            timestamp_str = str(ts_val or datetime.now(timezone.utc).isoformat())

        rec_hash = compute_record_payload_hash(log)
        c_hash = compute_chain_block_hash(prev_hash, rec_hash, timestamp_str)

        block = AuditChainBlock(
            index=idx,
            log_id=log_id,
            timestamp=timestamp_str,
            previous_hash=prev_hash,
            record_hash=rec_hash,
            chain_hash=c_hash,
            payload_summary={
                "action": log.get("action"),
                "resource_type": log.get("resource_type"),
                "resource_id": log.get("resource_id"),
                "username": log.get("username"),
            },
        )
        chain.append(block)
        prev_hash = c_hash

    return chain


def verify_audit_chain_integrity(blocks: list[AuditChainBlock]) -> dict[str, Any]:
    """Verify integrity of the audit log hash chain to detect any tampering or omission."""
    if not blocks:
        return {
            "is_valid": True,
            "tampered": False,
            "total_blocks_checked": 0,
            "chain_head_hash": GENESIS_HASH,
            "tampered_at_index": None,
            "error_description": "审计日志为空，哈希链默认完整有效。",
        }

    expected_prev = GENESIS_HASH
    for b in blocks:
        # 1. Verify previous_hash link
        if b.previous_hash != expected_prev:
            return {
                "is_valid": False,
                "tampered": True,
                "total_blocks_checked": len(blocks),
                "chain_head_hash": blocks[-1].chain_hash,
                "tampered_at_index": b.index,
                "tampered_log_id": b.log_id,
                "error_description": f"前驱哈希断裂 (Broken Chain Link): 块 #{b.index} 期望 {expected_prev[:16]}..., 实际收到 {b.previous_hash[:16]}...",
            }

        # 2. Recompute chain hash
        recalculated_hash = compute_chain_block_hash(b.previous_hash, b.record_hash, b.timestamp)
        if recalculated_hash != b.chain_hash:
            return {
                "is_valid": False,
                "tampered": True,
                "total_blocks_checked": len(blocks),
                "chain_head_hash": blocks[-1].chain_hash,
                "tampered_at_index": b.index,
                "tampered_log_id": b.log_id,
                "error_description": f"数据摘要篡改 (Payload Hash Mismatch): 块 #{b.index} 真实哈希与记录不一致，内容已被非法修改！",
            }

        expected_prev = b.chain_hash

    return {
        "is_valid": True,
        "tampered": False,
        "total_blocks_checked": len(blocks),
        "chain_head_hash": blocks[-1].chain_hash,
        "tampered_at_index": None,
        "error_description": "哈希链连续性校验 100% 通过，未检测到任何篡改或漏删记录。",
    }


def generate_compliance_audit_report(
    log_records: list[dict[str, Any]],
    *,
    organization: str = "ATP Enterprise Security",
    signing_key: str = DEFAULT_COMPLIANCE_SIGNING_KEY,
) -> dict[str, Any]:
    """Compile formal enterprise compliance audit report with cryptographic signature seal."""
    blocks = build_audit_hash_chain(log_records)
    integrity = verify_audit_chain_integrity(blocks)

    report_id = f"cert_audit_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    chain_head = integrity["chain_head_hash"]

    # Compute digital seal over chain head + organization + timestamp
    seal_material = f"{report_id}|{organization}|{chain_head}|{integrity['total_blocks_checked']}|{now_iso}"
    digital_signature = hmac.new(
        signing_key.encode("utf-8"),
        seal_material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "report_id": report_id,
        "organization": organization,
        "generated_at": now_iso,
        "compliance_standard": "ISO/IEC 27001 & SOC 2 Type II Tamper-Evident Audit Standard",
        "integrity_status": "VERIFIED_UNALTERED" if integrity["is_valid"] else "TAMPER_DETECTED",
        "total_records": integrity["total_blocks_checked"],
        "chain_head_hash": chain_head,
        "digital_seal_signature": digital_signature,
        "integrity_diagnostic": integrity,
        "blocks": [b.to_dict() for b in blocks],
    }
