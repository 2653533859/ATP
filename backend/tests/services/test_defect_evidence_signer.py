"""缺陷归因结论与 SLA 履约 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.defect_bidirectional_sync_gateway import (
    ExternalTicketPlatform,
    SyncActionType,
    SyncExecutionResult,
)
from app.services.defect_evidence_signer import (
    DefectArtifactType,
    DefectVerificationVerdict,
    canonicalize_payload,
    clear_defect_certificates,
    compute_evidence_sha256,
    get_defect_certificate,
    list_defect_certificates,
    sign_defect_artifact,
    sign_defect_cluster_group,
    sign_root_cause_attribution,
    sign_sla_compliance_evaluation,
    sign_sync_execution_audit,
    verify_defect_certificate,
)
from app.services.defect_root_cause_router import (
    AttributedResponsibility,
    DefectRootCauseType,
)
from app.services.defect_similarity_deduplicator import (
    ClusteredDefectGroup,
    DefectClusteringAction,
    TestCaseFailureRecord,
)
from app.services.defect_sla_escalation_watchdog import (
    DefectSLAEvaluationResult,
    DefectSeverity,
    SLAComplianceStatus,
    SLAEscalationAction,
)


@pytest.fixture(autouse=True)
def setup_certs():
    clear_defect_certificates()
    yield
    clear_defect_certificates()


def test_canonicalize_and_sha256():
    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    c1 = canonicalize_payload(d1)
    c2 = canonicalize_payload(d2)
    assert c1 == c2 == '{"a":1,"b":2}'

    sha = compute_evidence_sha256(c1)
    assert len(sha) == 64
    assert sha.islower()


def test_sign_and_verify_defect_cluster_group():
    failure = TestCaseFailureRecord(
        run_id="run_01",
        case_id="case_01",
        case_name="支付用例",
        error_message="timeout",
        stack_trace="trace",
    )
    cluster = ClusteredDefectGroup(
        cluster_id="cl_pay_01",
        primary_fingerprint="fp_hash_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        master_title="[payment-service] DatabaseConnectionTimeout",
        exception_type="DatabaseConnectionTimeout",
        target_service="payment-service",
        root_cause_file="/app/pay.py",
        total_failures_count=6,
        linked_case_ids=["case_01"],
        action=DefectClusteringAction.CREATED_NEW_MASTER,
        similarity_score=1.0,
        representative_failure=failure,
    )

    cert = sign_defect_cluster_group(cluster)
    assert cert.certificate_id.startswith("cert_def_")
    assert cert.artifact_type == DefectArtifactType.DEFECT_CLUSTER_GROUP
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    verdict, msg = verify_defect_certificate(cert.certificate_id)
    assert verdict == DefectVerificationVerdict.VALID
    assert "验签成功" in msg


def test_sign_root_cause_attribution():
    attr = AttributedResponsibility(
        attribution_id="attr_01",
        root_cause_type=DefectRootCauseType.DATABASE_TIMEOUT_OR_DEADLOCK,
        responsible_service="payment-service",
        responsible_team="资金结算组",
        suggested_assignee="lead_pay@atp.io",
        suggested_assignee_name="李强",
        attribution_confidence_pct=95.0,
        root_cause_summary="数据库死锁超时",
        evidence_chain=["证据1", "证据2"],
    )

    cert = sign_root_cause_attribution(attr)
    assert cert.artifact_type == DefectArtifactType.ROOT_CAUSE_ATTRIBUTION
    assert cert.summary["responsible_service"] == "payment-service"

    verdict, _ = verify_defect_certificate(cert.certificate_id)
    assert verdict == DefectVerificationVerdict.VALID


def test_sign_sync_execution_audit():
    sync_res = SyncExecutionResult(
        sync_id="sync_01",
        defect_id="DEF-1001",
        platform=ExternalTicketPlatform.JIRA,
        external_ticket_key="JIRA-4021",
        action_taken=SyncActionType.AUTO_RESOLVED_ON_PASS,
        previous_state="OPEN",
        new_state="CLOSED",
        sync_message="回归通过自动标记闭环",
    )

    cert = sign_sync_execution_audit(sync_res)
    assert cert.artifact_type == DefectArtifactType.SYNC_EXECUTION_AUDIT

    verdict, _ = verify_defect_certificate(cert.certificate_id)
    assert verdict == DefectVerificationVerdict.VALID


def test_sign_sla_compliance_evaluation():
    sla_eval = DefectSLAEvaluationResult(
        tracking_id="sla_01",
        defect_id="DEF-1001",
        severity=DefectSeverity.P0_BLOCKING,
        compliance_status=SLAComplianceStatus.HEALTHY_ON_TRACK,
        escalation_action=SLAEscalationAction.NO_ACTION,
        elapsed_hours=5.0,
        max_allowed_resolution_hours=24.0,
        remaining_hours=19.0,
        is_release_blocked=False,
        escalation_notice="正常推进",
    )

    cert = sign_sla_compliance_evaluation(sla_eval)
    assert cert.artifact_type == DefectArtifactType.SLA_COMPLIANCE_EVALUATION

    verdict, _ = verify_defect_certificate(cert.certificate_id)
    assert verdict == DefectVerificationVerdict.VALID


def test_verify_tampered_payload_and_signature():
    cert = sign_defect_artifact(
        artifact_type=DefectArtifactType.DEFECT_CLUSTER_GROUP,
        artifact_id="art_1",
        target_service="pay",
        payload={"failures": 10},
        summary={},
    )

    # 篡改 payload
    cert.canonical_payload["failures"] = 999
    verdict, msg = verify_defect_certificate(cert.certificate_id)
    assert verdict == DefectVerificationVerdict.TAMPERED_INVALID
    assert "指纹不匹配" in msg

    # 恢复数据并篡改签名
    cert.canonical_payload["failures"] = 10
    cert.hmac_signature = "bad" * 21 + "b"
    verdict_sig, msg_sig = verify_defect_certificate(cert.certificate_id)
    assert verdict_sig == DefectVerificationVerdict.TAMPERED_INVALID
    assert "数字签名无效" in msg_sig


def test_verify_nonexistent_certificate():
    verdict, msg = verify_defect_certificate("cert_def_not_found_999")
    assert verdict == DefectVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未检索到" in msg


def test_list_and_get_certificates():
    sign_defect_artifact(
        artifact_type=DefectArtifactType.DEFECT_CLUSTER_GROUP,
        artifact_id="a1",
        target_service="payment-service",
        payload={"k": 1},
        summary={},
    )
    cert2 = sign_defect_artifact(
        artifact_type=DefectArtifactType.DEFECT_CLUSTER_GROUP,
        artifact_id="a2",
        target_service="auth-service",
        payload={"k": 2},
        summary={},
    )

    all_certs = list_defect_certificates()
    assert len(all_certs) == 2

    pay_certs = list_defect_certificates(target_service="payment-service")
    assert len(pay_certs) == 1

    fetched = get_defect_certificate(cert2.certificate_id)
    assert fetched is not None
    assert fetched.artifact_id == "a2"
