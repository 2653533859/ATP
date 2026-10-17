"""调度决策与集群容量 64 位 SHA-256 存证服务单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.fleet_concurrency_router import (
    CandidateDeviceEvaluation,
    RoutingDecisionResult,
    RoutingStatus,
)
from app.services.scheduler_evidence_signer import (
    SchedulerArtifactType,
    SchedulerVerificationVerdict,
    clear_scheduler_certificates,
    get_scheduler_certificate,
    list_scheduler_certificates,
    sign_capacity_snapshot_evidence,
    sign_routing_decision_evidence,
    verify_scheduler_certificate,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_scheduler_certificates()
    yield
    clear_scheduler_certificates()


def test_sign_routing_decision_and_verify():
    dec = RoutingDecisionResult(
        decision_id="route_ev_test_01",
        task_id="task_checkout_01",
        target_platform="ios",
        status=RoutingStatus.ROUTED,
        selected_device_id="00008101-IPHONE-01",
        fitness_score=94.5,
        candidate_evaluations=[
            CandidateDeviceEvaluation("00008101-IPHONE-01", "ios", True, "", 95.0, 100.0, 100.0, 50.0, 94.5),
        ],
        routing_reason="全局最优匹配",
    )

    cert = sign_routing_decision_evidence(dec)
    assert cert.certificate_id.startswith("cert_route_")
    assert cert.artifact_type == SchedulerArtifactType.ROUTING_DECISION
    assert cert.artifact_id == "route_ev_test_01"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 查验在线验签通过
    verdict, reason = verify_scheduler_certificate(cert.certificate_id)
    assert verdict == SchedulerVerificationVerdict.VALID
    assert "无篡改" in reason


def test_sign_capacity_snapshot_and_verify():
    cap = {
        "total_devices": 10,
        "healthy_count": 8,
        "total_capacity": 20,
        "used_concurrency": 6,
        "available_capacity": 14,
        "cluster_averages": {"avg_temperature_c": 33.2},
    }

    cert = sign_capacity_snapshot_evidence("snap_ev_02", cap)
    assert cert.artifact_type == SchedulerArtifactType.CAPACITY_SNAPSHOT
    assert cert.artifact_id == "snap_ev_02"
    assert len(cert.evidence_sha256) == 64

    verdict, _ = verify_scheduler_certificate(cert.certificate_id)
    assert verdict == SchedulerVerificationVerdict.VALID


def test_tamper_detection_on_canonical_payload():
    dec = RoutingDecisionResult(
        decision_id="route_tamper_03",
        task_id="task_tamper",
        target_platform="android",
        status=RoutingStatus.ROUTED,
        selected_device_id="dev_and_01",
        fitness_score=90.0,
        candidate_evaluations=[],
        routing_reason="通过",
    )

    cert = sign_routing_decision_evidence(dec)

    # 模拟外部篡改载荷字段 (如篡改选中真机)
    cert.canonical_payload["selected_device_id"] = "hacked_device_99"

    verdict, reason = verify_scheduler_certificate(cert.certificate_id)
    assert verdict == SchedulerVerificationVerdict.TAMPERED_INVALID
    assert "存证指纹被篡改" in reason


def test_tamper_detection_on_hmac_signature():
    dec = RoutingDecisionResult(
        decision_id="route_sig_tamper_04",
        task_id="task_sig",
        target_platform="ios",
        status=RoutingStatus.ROUTED,
        selected_device_id="dev_ios_01",
        fitness_score=88.0,
        candidate_evaluations=[],
        routing_reason="通过",
    )

    cert = sign_routing_decision_evidence(dec)

    # 篡改 HMAC 防伪签名
    cert.hmac_signature = "bad" + cert.hmac_signature[3:]

    verdict, reason = verify_scheduler_certificate(cert.certificate_id)
    assert verdict == SchedulerVerificationVerdict.TAMPERED_INVALID
    assert "防伪数字签名校验失败" in reason


def test_certificate_not_found_and_listing():
    verdict, _ = verify_scheduler_certificate("cert_non_existent")
    assert verdict == SchedulerVerificationVerdict.CERTIFICATE_NOT_FOUND

    assert get_scheduler_certificate("cert_non_existent") is None
    assert isinstance(list_scheduler_certificates(), list)
