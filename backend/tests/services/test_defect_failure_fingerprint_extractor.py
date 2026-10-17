"""失败堆栈与异常语义指纹提取器单测 (T1.1)"""

from __future__ import annotations

from app.services.defect_failure_fingerprint_extractor import (
    extract_failure_fingerprint,
    sanitize_dynamic_tokens,
)


def test_sanitize_dynamic_tokens():
    raw_str = (
        "Object at 0x7f9a8b1c4320 with task_550e8400-e29b-41d4-a716-446655440000 "
        "failed at 2026-10-18T14:30:00Z connecting to 10.0.0.1:8080 (user_a1b2c3d4)"
    )
    cleaned = sanitize_dynamic_tokens(raw_str)
    assert "0x7f9a8b1c4320" not in cleaned
    assert "<HEX_ADDR>" in cleaned
    assert "<UUID>" in cleaned
    assert "<TIMESTAMP>" in cleaned
    assert "<HOST:PORT>" in cleaned
    assert "user_<ID>" in cleaned


def test_same_root_cause_generates_identical_fingerprint():
    # 模拟两次不同时刻、不同临时地址和用例 ID 的同源失败
    stack_a = """Traceback (most recent call last):
  File "/opt/venv/lib/python3.12/site-packages/pytest/runner.py", line 120, in run
    item.runtest()
  File "/workspace/backend/app/services/payment.py", line 45, in execute_charge
    raise DatabaseConnectionTimeout("Failed to connect 10.0.0.1:5432 after 3000ms at 0x7fa123")
DatabaseConnectionTimeout: Connection timeout on 10.0.0.1:5432 at 2026-10-18 10:00:00 (order_112233)
"""

    stack_b = """Traceback (most recent call last):
  File "/opt/venv/lib/python3.12/site-packages/pytest/runner.py", line 120, in run
    item.runtest()
  File "/workspace/backend/app/services/payment.py", line 45, in execute_charge
    raise DatabaseConnectionTimeout("Failed to connect 10.0.0.2:5432 after 3000ms at 0x99bb88")
DatabaseConnectionTimeout: Connection timeout on 10.0.0.2:5432 at 2026-10-18 15:30:00 (order_445566)
"""

    res_a = extract_failure_fingerprint(
        raw_error_message="DatabaseConnectionTimeout on host",
        raw_stack_trace=stack_a,
    )
    res_b = extract_failure_fingerprint(
        raw_error_message="DatabaseConnectionTimeout on host",
        raw_stack_trace=stack_b,
    )

    assert len(res_a.failure_fingerprint) == 64
    assert res_a.failure_fingerprint == res_b.failure_fingerprint
    assert res_a.exception_type == "DatabaseConnectionTimeout"
    assert res_a.root_cause_frame is not None
    assert "payment.py" in res_a.root_cause_frame.file_path
    assert res_a.root_cause_frame.function_name == "execute_charge"


def test_different_errors_generate_distinct_fingerprints():
    stack_pay = """  File "/app/services/payment.py", line 10, in pay
    raise PaymentDeclinedError("Insufficient balance")"""
    stack_auth = """  File "/app/services/auth.py", line 20, in verify
    raise UnauthorizedAccessError("Token expired")"""

    res_pay = extract_failure_fingerprint(
        raw_error_message="PaymentDeclinedError: Insufficient balance",
        raw_stack_trace=stack_pay,
    )
    res_auth = extract_failure_fingerprint(
        raw_error_message="UnauthorizedAccessError: Token expired",
        raw_stack_trace=stack_auth,
    )

    assert res_pay.failure_fingerprint != res_auth.failure_fingerprint
    assert res_pay.exception_type == "PaymentDeclinedError"
    assert res_auth.exception_type == "UnauthorizedAccessError"

    d = res_pay.to_dict()
    assert d["exception_type"] == "PaymentDeclinedError"
    assert len(d["failure_fingerprint"]) == 64
