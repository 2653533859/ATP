"""追踪审计凭据 64 位 SHA-256 防篡改存证服务单测 (T4.2)"""

from __future__ import annotations

from app.services.trace_evidence_fingerprint_signer import (
    clear_evidence_store,
    get_evidence_certificate,
    list_evidence_certificates,
    sign_trace_evidence,
    verify_trace_evidence,
)


def test_sign_and_verify_trace_evidence():
    clear_evidence_store()

    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    run_id = "run_audit_001"

    spans = [
        {
            "span_id": "span_root",
            "service_name": "gateway",
            "name": "POST /order",
            "duration_ms": 120.0,
            "status": {"code": "OK"},
            "attributes": {"http.status_code": 200},
        },
        {
            "span_id": "span_sub",
            "parent_span_id": "span_root",
            "service_name": "order-service",
            "name": "CreateOrder",
            "duration_ms": 80.0,
            "status": {"code": "OK"},
            "attributes": {"order_id": 998},
        },
    ]

    # 1. 签名存证
    cert = sign_trace_evidence(trace_id=trace_id, run_id=run_id, spans=spans)
    assert cert.trace_id == trace_id
    assert cert.run_id == run_id
    assert cert.spans_count == 2
    assert cert.algorithm == "SHA-256"
    assert len(cert.evidence_sha256) == 64  # 标准 64 字符十六进制哈希
    assert len(cert.hmac_signature) == 64

    # 2. 正常验签
    is_valid, msg = verify_trace_evidence(certificate=cert.to_dict(), spans=spans)
    assert is_valid is True
    assert "EVIDENCE_VERIFIED" in msg

    # 3. 篡改测试 A: 修改持续耗时 (哪怕改动 1ms)
    tampered_duration = [
        dict(spans[0], duration_ms=121.0),  # 篡改
        spans[1],
    ]
    is_valid, msg = verify_trace_evidence(certificate=cert.to_dict(), spans=tampered_duration)
    assert is_valid is False
    assert "TAMPERED_HASH_MISMATCH" in msg

    # 4. 篡改测试 B: 修改属性或状态码
    tampered_status = [
        spans[0],
        dict(spans[1], attributes={"order_id": 999}),  # 篡改订单号
    ]
    is_valid, msg = verify_trace_evidence(certificate=cert.to_dict(), spans=tampered_status)
    assert is_valid is False
    assert "TAMPERED_HASH_MISMATCH" in msg

    # 5. 存储与列表查询
    stored = get_evidence_certificate(trace_id)
    assert stored is not None
    assert stored["evidence_sha256"] == cert.evidence_sha256

    items = list_evidence_certificates(limit=10)
    assert len(items) == 1
