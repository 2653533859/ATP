"""大模型评测结论与红蓝攻防验收 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.llm_eval_safety_boundary_guard import (
    LlmAdmissionRequest,
    LlmAdmissionTicket,
    evaluate_llm_safety_admission,
)
from app.services.llm_evidence_signer import (
    LlmArtifactType,
    LlmVerificationVerdict,
    clear_llm_certificates,
    compute_canonical_json,
    compute_evidence_sha256,
    compute_hmac_signature,
    get_llm_certificate,
    list_llm_certificates,
    sign_hallucination_report,
    sign_rag_triad_report,
    sign_red_team_report,
    sign_safety_admission_verdict,
    verify_llm_certificate,
)
from app.services.llm_hallucination_detector import detect_llm_hallucinations
from app.services.llm_rag_triad_evaluator import evaluate_rag_triad
from app.services.llm_red_teaming_attacker import (
    aggregate_red_team_report,
    evaluate_model_defense,
    generate_adversarial_payloads,
)


@pytest.fixture(autouse=True)
def _clean_cert_store():
    clear_llm_certificates()
    yield
    clear_llm_certificates()


def test_canonical_json_determinism():
    """测试 Canonical JSON 确定性序列化规范 (字典乱序产出一致性)"""
    d1 = {"model": "qwen-2.5-72b", "rag_score": 94.2, "tokens": 1024}
    d2 = {"tokens": 1024, "model": "qwen-2.5-72b", "rag_score": 94.2}

    c1 = compute_canonical_json(d1)
    c2 = compute_canonical_json(d2)

    assert c1 == c2
    assert c1 == '{"model":"qwen-2.5-72b","rag_score":94.2,"tokens":1024}'

    sha1 = compute_evidence_sha256(c1)
    sha2 = compute_evidence_sha256(c2)
    assert sha1 == sha2
    assert len(sha1) == 64
    sig = compute_hmac_signature(c1)
    assert len(sig) == 64


def test_sign_rag_triad_report():
    """测试为 RAG 三元组评测结论签发 64 位 SHA-256 存证证书"""
    report = evaluate_rag_triad(
        query="ATP 压测隔离机制？",
        contexts=["所有压测写操作自动路由至 t_order_shadow 影子表。"],
        answer="写操作路由至 t_order_shadow 影子表物理隔离。",
    )

    cert = sign_rag_triad_report(report, target_model="qwen-2.5-72b")

    assert cert.artifact_type == LlmArtifactType.RAG_TRIAD_EVALUATION
    assert cert.target_model == "qwen-2.5-72b"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64
    assert cert.summary["grade"] in ("EXCELLENT", "GOOD", "MARGINAL", "POOR")

    fetched = get_llm_certificate(cert.certificate_id)
    assert fetched is not None
    assert fetched.evidence_sha256 == cert.evidence_sha256
    # 在线验签校验
    verdict, note = verify_llm_certificate(cert.certificate_id)
    assert verdict == LlmVerificationVerdict.VALID
    assert "无篡改痕迹" in (note or "")


def test_sign_hallucination_report():
    """测试为事实一致性与幻觉检出报告签发存证证书"""
    report = detect_llm_hallucinations(
        query="发压模式有哪些？",
        answer="支持阶梯爬坡模式。",
        golden_facts=["系统支持阶梯递进爬坡与恒定稳态并发模式。"],
        model_name="deepseek-v3",
    )

    cert = sign_hallucination_report(report, target_model="deepseek-v3")

    assert cert.artifact_type == LlmArtifactType.HALLUCINATION_AUDIT_REPORT
    assert cert.target_model == "deepseek-v3"
    assert len(cert.evidence_sha256) == 64

    verdict, _ = verify_llm_certificate(cert.certificate_id)
    assert verdict == LlmVerificationVerdict.VALID


def test_sign_red_team_report():
    """测试为红蓝越狱对抗渗透报告签发存证证书"""
    payloads = generate_adversarial_payloads("测试指令")[:2]
    res1 = evaluate_model_defense(payloads[0], "抱歉，我无法回答该问题。")
    res2 = evaluate_model_defense(payloads[1], "作为一个 AI 助手，我不能执行该操作。")
    report = aggregate_red_team_report("llama-3.3-70b", [res1, res2])

    cert = sign_red_team_report(report)

    assert cert.artifact_type == LlmArtifactType.RED_TEAM_ROBUSTNESS_REPORT
    assert cert.target_model == "llama-3.3-70b"
    assert len(cert.evidence_sha256) == 64

    verdict, _ = verify_llm_certificate(cert.certificate_id)
    assert verdict == LlmVerificationVerdict.VALID


def test_sign_safety_admission_verdict():
    """测试为生产安全强准入放行裁决签发存证证书"""
    ticket = LlmAdmissionTicket(
        ticket_key="OA-LLM-20261019-999",
        status="APPROVED",
        approver="sec_architect",
        composite_score=95.0,
        red_team_defense_rate=98.0,
    )
    req = LlmAdmissionRequest(
        model_name="deepseek-r1",
        environment="production",
        caller_service="payment-agent",
        ticket=ticket,
        security_token="LLM_SEC_TOKEN_20261019_PROD_123456",
    )
    verdict = evaluate_llm_safety_admission(req)
    cert = sign_safety_admission_verdict(verdict)

    assert cert.artifact_type == LlmArtifactType.LLM_SAFETY_ADMISSION_VERDICT
    assert cert.target_model == "deepseek-r1"
    assert len(cert.evidence_sha256) == 64

    ver_result, _ = verify_llm_certificate(cert.certificate_id)
    assert ver_result == LlmVerificationVerdict.VALID


def test_verify_certificate_tampered_payload():
    """测试证据载荷遭到恶意篡改时敏锐检出 TAMPERED_INVALID"""
    report = evaluate_rag_triad("Query", ["Context"], "Answer")
    cert = sign_rag_triad_report(report)

    # 恶意篡改存证中的评分字段
    cert.canonical_payload["composite_score"] = 999.9

    verdict, note = verify_llm_certificate(cert.certificate_id)
    assert verdict == LlmVerificationVerdict.TAMPERED_INVALID
    assert "SHA-256 指纹不匹配" in (note or "")


def test_verify_certificate_tampered_signature():
    """测试防伪数字签名遭到伪造时检出 TAMPERED_INVALID"""
    report = evaluate_rag_triad("Query", ["Context"], "Answer")
    cert = sign_rag_triad_report(report)

    # 伪造数字签名
    cert.hmac_signature = "0000000000000000000000000000000000000000000000000000000000000000"

    verdict, note = verify_llm_certificate(cert.certificate_id)
    assert verdict == LlmVerificationVerdict.TAMPERED_INVALID
    assert "HMAC 防伪签名失效" in (note or "")


def test_verify_certificate_not_found():
    """测试未检索到证书时的边界判定"""
    verdict, note = verify_llm_certificate("non_existent_cert_id")
    assert verdict == LlmVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未检索到证书" in (note or "")


def test_list_and_clear_certificates():
    """测试存证证书列表检索与类型过滤"""
    rep1 = evaluate_rag_triad("Q1", ["C1"], "A1")
    sign_rag_triad_report(rep1, target_model="model-a")

    rep2 = detect_llm_hallucinations("Q2", "A2", ["Fact"], "model-b")
    sign_hallucination_report(rep2, target_model="model-b")

    all_certs = list_llm_certificates()
    assert len(all_certs) == 2

    rag_certs = list_llm_certificates(artifact_type=LlmArtifactType.RAG_TRIAD_EVALUATION)
    assert len(rag_certs) == 1
    assert rag_certs[0].artifact_type == LlmArtifactType.RAG_TRIAD_EVALUATION

    clear_llm_certificates()
    assert len(list_llm_certificates()) == 0


def test_certificate_store_capacity_eviction(monkeypatch):
    """测试存证证书内存库超出最大容量时自动按 FIFO 淘汰最早证书"""
    import app.services.llm_evidence_signer as signer_mod

    clear_llm_certificates()
    monkeypatch.setattr(signer_mod, "MAX_LLM_CERT_STORE_CAPACITY", 3)

    rep = evaluate_rag_triad("Q", ["C"], "A")
    c1 = sign_rag_triad_report(rep, target_model="m1")
    c2 = sign_rag_triad_report(rep, target_model="m2")
    c3 = sign_rag_triad_report(rep, target_model="m3")
    assert len(list_llm_certificates()) == 3
    assert get_llm_certificate(c1.certificate_id) is not None

    # 签发第 4 个，c1 应该被淘汰
    c4 = sign_rag_triad_report(rep, target_model="m4")
    assert len(list_llm_certificates()) == 3
    assert get_llm_certificate(c1.certificate_id) is None
    assert get_llm_certificate(c2.certificate_id) is not None
    assert get_llm_certificate(c4.certificate_id) is not None
