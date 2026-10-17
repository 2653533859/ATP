"""工作流执行证据链 64 位 SHA-256 签名存证服务单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.workflow_evidence_fingerprint_signer import (
    clear_workflow_certificates,
    get_workflow_certificate,
    list_workflow_certificates,
    sign_workflow_evidence,
    verify_workflow_evidence,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_workflow_certificates()
    yield
    clear_workflow_certificates()


def test_sign_and_verify_workflow_evidence():
    run_id = "wfrun_audit_001"
    wf_id = "wf_payment_e2e"

    report = {
        "workflow_id": wf_id,
        "run_id": run_id,
        "status": "SUCCESS",
        "executed_nodes_count": 3,
        "node_records": [
            {"node_id": "step_1", "status": "SUCCESS", "duration_ms": 35.0},
            {"node_id": "step_2", "status": "SUCCESS", "duration_ms": 120.0},
            {"node_id": "step_3", "status": "SUCCESS", "duration_ms": 40.0},
        ],
    }

    # 1. 签名存证
    cert = sign_workflow_evidence(report, signer="atp-qa-auditor")
    assert cert.workflow_id == wf_id
    assert cert.run_id == run_id
    assert len(cert.evidence_sha256) == 64  # 64 位 SHA-256 字符串
    assert len(cert.hmac_signature) == 64

    # 2. 正常验签
    is_valid, msg = verify_workflow_evidence(cert.to_dict(), report)
    assert is_valid is True
    assert "EVIDENCE_VERIFIED" in msg

    # 3. 篡改测试: 修改节点耗时 1ms
    tampered_dur = {
        "workflow_id": wf_id,
        "run_id": run_id,
        "status": "SUCCESS",
        "node_records": [
            {"node_id": "step_1", "status": "SUCCESS", "duration_ms": 36.0},  # 篡改
            {"node_id": "step_2", "status": "SUCCESS", "duration_ms": 120.0},
            {"node_id": "step_3", "status": "SUCCESS", "duration_ms": 40.0},
        ],
    }
    is_valid, msg = verify_workflow_evidence(cert.to_dict(), tampered_dur)
    assert is_valid is False
    assert "TAMPERED_HASH_MISMATCH" in msg

    # 4. 存储与查询
    stored = get_workflow_certificate(run_id)
    assert stored is not None
    assert stored.evidence_sha256 == cert.evidence_sha256
    assert len(list_workflow_certificates()) == 1
