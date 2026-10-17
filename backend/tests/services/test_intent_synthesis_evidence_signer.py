"""AI 生成与探索证据 64 位 SHA-256 存证服务单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.intent_synthesis_evidence_signer import (
    ArtifactType,
    VerificationVerdict,
    clear_evidence_certificates,
    get_evidence_certificate,
    list_evidence_certificates,
    sign_exploration_trajectory_evidence,
    sign_intent_workflow_evidence,
    verify_evidence_certificate,
)
from app.services.intent_workflow_synthesizer import (
    IntentSemanticSlots,
    SynthesizedWorkflowDAG,
    WorkflowNode,
)
from app.services.hybrid_workflow_dag_engine import WorkflowNodeType
from app.services.vlm_autonomous_explorer import (
    ExplorationActionType,
    ExplorationSession,
    StateTransitionEdge,
    UIStateNode,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_evidence_certificates()
    yield
    clear_evidence_certificates()


def test_sign_intent_workflow_and_verify_valid():
    dag = SynthesizedWorkflowDAG(
        synthesis_id="syn_test_evidence_001",
        workflow_id="wf_001",
        workflow_name="电商端到端综合测试工作流",
        semantic_summary="由意图推导生成",
        nodes=[
            WorkflowNode(node_id="n1", node_name="HTTP 创建订单", node_type=WorkflowNodeType.HTTP_REQUEST),
            WorkflowNode(node_id="n2", node_name="iOS 支付", node_type=WorkflowNodeType.MOBILE_IOS),
        ],
        edges=[],
        variable_bindings={"n2": "{{n1.output.body.order_id}}"},
        slots=IntentSemanticSlots(
            raw_prompt="接口创建订单后在 iOS 完成支付",
            business_domain="ecommerce",
            protocols=["HTTP", "iOS"],
            actions=["create", "pay"],
            extracted_entities=["order_id"],
            suggested_node_count=2,
            analyzed_at="2026-10-17T12:00:00Z",
        ),
    )

    cert = sign_intent_workflow_evidence(dag)

    assert cert.certificate_id.startswith("cert_aiwf_")
    assert cert.artifact_type == ArtifactType.INTENT_WORKFLOW
    assert cert.artifact_id == "syn_test_evidence_001"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 查验在线验签
    verdict, reason = verify_evidence_certificate(cert.certificate_id)
    assert verdict == VerificationVerdict.VALID
    assert "未被任何篡改" in reason


def test_sign_exploration_trajectory_and_verify():
    sess = ExplorationSession(
        session_id="expsess_test_evidence_002",
        platform="ios",
        device_id="00008101-IPHONE",
        goal="探索商城加购流程",
        status="COMPLETED",
        states={
            "s1": UIStateNode("s1", "首页", "sig_1", [], 1),
        },
        transitions=[
            StateTransitionEdge("t1", "s1", "s1", ExplorationActionType.TAP, "加购按钮"),
        ],
    )

    cert = sign_exploration_trajectory_evidence(sess)
    assert cert.artifact_type == ArtifactType.EXPLORATION_TRAJECTORY
    assert cert.artifact_id == "expsess_test_evidence_002"
    assert len(cert.evidence_sha256) == 64

    verdict, _ = verify_evidence_certificate(cert.certificate_id)
    assert verdict == VerificationVerdict.VALID


def test_tamper_detection_triggers_tampered_invalid():
    dag = SynthesizedWorkflowDAG(
        synthesis_id="syn_tamper_test",
        workflow_id="wf_tamper",
        workflow_name="合规工作流原始态",
        semantic_summary="测试",
        nodes=[],
        edges=[],
        variable_bindings={},
        slots=IntentSemanticSlots(
            raw_prompt="测试 Prompt",
            business_domain="fintech",
            protocols=["HTTP"],
            actions=["audit"],
            extracted_entities=[],
            suggested_node_count=1,
            analyzed_at="2026-10-17T12:00:00Z",
        ),
    )

    cert = sign_intent_workflow_evidence(dag)

    # 模拟恶意篡改载荷内容
    cert.canonical_payload["workflow_name"] = "已被黑客篡改的工作流"

    verdict, reason = verify_evidence_certificate(cert.certificate_id)
    assert verdict == VerificationVerdict.TAMPERED_INVALID
    assert "存证指纹不匹配" in reason


def test_signature_tamper_detection():
    dag = SynthesizedWorkflowDAG(
        synthesis_id="syn_sig_tamper_test",
        workflow_id="wf_sig_tamper",
        workflow_name="测试工作流",
        semantic_summary="测试",
        nodes=[],
        edges=[],
        variable_bindings={},
        slots=IntentSemanticSlots(
            raw_prompt="测试 Prompt",
            business_domain="fintech",
            protocols=["HTTP"],
            actions=["audit"],
            extracted_entities=[],
            suggested_node_count=1,
            analyzed_at="2026-10-17T12:00:00Z",
        ),
    )

    cert = sign_intent_workflow_evidence(dag)

    # 篡改 HMAC 签名
    cert.hmac_signature = "bad" + cert.hmac_signature[3:]

    verdict, reason = verify_evidence_certificate(cert.certificate_id)
    assert verdict == VerificationVerdict.TAMPERED_INVALID
    assert "防伪签名校验失败" in reason


def test_certificate_not_found_and_list():
    verdict, _ = verify_evidence_certificate("cert_non_existent")
    assert verdict == VerificationVerdict.CERTIFICATE_NOT_FOUND

    assert get_evidence_certificate("cert_non_existent") is None
    assert isinstance(list_evidence_certificates(), list)
