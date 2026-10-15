"""Unit tests for T4.3 Tamper-Evident SHA-256 Audit Log Hash Chain & Compliance Certification.

Tests:
1. build_audit_hash_chain links blocks with previous_hash and deterministic SHA-256 digests
2. verify_audit_chain_integrity passes on untampered sequence
3. verify_audit_chain_integrity detects payload modification
4. verify_audit_chain_integrity detects record deletion / broken chain links
5. generate_compliance_audit_report produces HMAC-SHA256 digital signature seal
"""

from __future__ import annotations

from app.services.audit_tamper_evident_chain import (
    GENESIS_HASH,
    build_audit_hash_chain,
    compute_chain_block_hash,
    generate_compliance_audit_report,
    verify_audit_chain_integrity,
)


def _sample_logs():
    return [
        {
            "id": 1,
            "action": "user_login",
            "resource_type": "user",
            "resource_id": 101,
            "username": "admin",
            "ip_address": "127.0.0.1",
            "project_id": None,
            "created_at": "2026-10-16T10:00:00Z",
        },
        {
            "id": 2,
            "action": "case_create",
            "resource_type": "case",
            "resource_id": 501,
            "username": "tester_bob",
            "ip_address": "192.168.1.50",
            "project_id": 1,
            "created_at": "2026-10-16T10:05:00Z",
        },
        {
            "id": 3,
            "action": "chaos_experiment_start",
            "resource_type": "mesh_chaos",
            "resource_id": 901,
            "username": "engineer_alice",
            "ip_address": "192.168.1.60",
            "project_id": 1,
            "created_at": "2026-10-16T10:15:00Z",
        },
    ]


def test_build_audit_hash_chain():
    logs = _sample_logs()
    blocks = build_audit_hash_chain(logs)

    assert len(blocks) == 3
    # Genesis link
    assert blocks[0].previous_hash == GENESIS_HASH
    assert blocks[0].index == 1

    # Consecutive links
    assert blocks[1].previous_hash == blocks[0].chain_hash
    assert blocks[2].previous_hash == blocks[1].chain_hash

    # Verify chain hash matches formula
    expected_block0_hash = compute_chain_block_hash(
        blocks[0].previous_hash,
        blocks[0].record_hash,
        blocks[0].timestamp,
    )
    assert blocks[0].chain_hash == expected_block0_hash


def test_verify_audit_chain_integrity_valid():
    blocks = build_audit_hash_chain(_sample_logs())
    result = verify_audit_chain_integrity(blocks)

    assert result["is_valid"] is True
    assert result["tampered"] is False
    assert result["total_blocks_checked"] == 3
    assert result["tampered_at_index"] is None


def test_verify_audit_chain_integrity_tamper_payload():
    blocks = build_audit_hash_chain(_sample_logs())

    # Simulate malicious attacker tampering with block #2 payload
    blocks[1].record_hash = "deadbeef" * 8

    result = verify_audit_chain_integrity(blocks)
    assert result["is_valid"] is False
    assert result["tampered"] is True
    assert result["tampered_at_index"] == 2
    assert result["tampered_log_id"] == 2
    assert "Payload Hash Mismatch" in result["error_description"]


def test_verify_audit_chain_integrity_tamper_deletion():
    blocks = build_audit_hash_chain(_sample_logs())

    # Malicious attacker deletes block #2 (leaving #1 and #3)
    del blocks[1]

    result = verify_audit_chain_integrity(blocks)
    assert result["is_valid"] is False
    assert result["tampered"] is True
    assert "Broken Chain Link" in result["error_description"]


def test_generate_compliance_audit_report():
    logs = _sample_logs()
    report = generate_compliance_audit_report(
        logs,
        organization="Enterprise Audit Compliance Unit",
    )

    assert "report_id" in report
    assert report["organization"] == "Enterprise Audit Compliance Unit"
    assert report["integrity_status"] == "VERIFIED_UNALTERED"
    assert report["total_records"] == 3
    assert len(report["digital_seal_signature"]) == 64  # SHA-256 HMAC
    assert len(report["blocks"]) == 3
