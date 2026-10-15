"""Unit tests for T2.1 W3C TraceContext and traceparent protocol auto-injection.

Tests:
1. generate_w3c_traceparent formats compliant 00-{trace_id}-{span_id}-{flags}
2. normalize_w3c_trace_id normalizes arbitrary raw IDs into 32-hex lowercase strings
3. build_w3c_tracestate constructs vendor-specific ATP execution context
4. inject_w3c_trace_headers injects traceparent and tracestate without overwriting explicit headers
5. Case-insensitive header preservation
"""

from __future__ import annotations

import re

from app.core.tracing import (
    build_w3c_tracestate,
    generate_w3c_span_id,
    generate_w3c_traceparent,
    inject_w3c_trace_headers,
    normalize_w3c_trace_id,
)

W3C_TRACEPARENT_REGEX = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-(01|00)$")


def test_normalize_w3c_trace_id():
    # 32-hex string preserved
    tid_32 = "4bf92f3577b34da6a3ce929d0e0e4736"
    assert normalize_w3c_trace_id(tid_32) == tid_32

    # 16-hex string doubled to 32-hex
    tid_16 = "0123456789abcdef"
    assert normalize_w3c_trace_id(tid_16) == f"{tid_16}{tid_16}"

    # UUID with dashes cleaned
    uuid_str = "4bf92f35-77b3-4da6-a3ce-929d0e0e4736"
    assert normalize_w3c_trace_id(uuid_str) == tid_32

    # Arbitrary non-hex string hashed to 32-hex
    hashed = normalize_w3c_trace_id("non-hex-custom-id")
    assert len(hashed) == 32
    assert all(c in "0123456789abcdef" for c in hashed)


def test_generate_w3c_traceparent():
    tp_sampled = generate_w3c_traceparent(sampled=True)
    assert W3C_TRACEPARENT_REGEX.match(tp_sampled) is not None
    assert tp_sampled.endswith("-01")

    tp_unsampled = generate_w3c_traceparent(sampled=False)
    assert W3C_TRACEPARENT_REGEX.match(tp_unsampled) is not None
    assert tp_unsampled.endswith("-00")

    # Specific trace_id and span_id
    tid = "11223344556677881122334455667788"
    sid = "aabbccddeeff0011"
    tp_custom = generate_w3c_traceparent(trace_id=tid, span_id=sid, sampled=True)
    assert tp_custom == f"00-{tid}-{sid}-01"


def test_generate_w3c_span_id():
    sid = generate_w3c_span_id()
    assert len(sid) == 16
    assert all(c in "0123456789abcdef" for c in sid)


def test_build_w3c_tracestate():
    assert build_w3c_tracestate(run_id=101, case_id=42) == "atp=r:101;c:42"
    assert build_w3c_tracestate(run_id=88) == "atp=r:88"
    assert build_w3c_tracestate(case_id=99) == "atp=c:99"
    assert build_w3c_tracestate() == "atp=1"


def test_inject_w3c_trace_headers_adds_missing_headers():
    headers = {"Content-Type": "application/json", "Authorization": "Bearer token"}
    injected = inject_w3c_trace_headers(
        headers,
        run_id=200,
        case_id=30,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    )

    assert "traceparent" in injected
    assert W3C_TRACEPARENT_REGEX.match(injected["traceparent"]) is not None
    assert "4bf92f3577b34da6a3ce929d0e0e4736" in injected["traceparent"]
    assert injected["tracestate"] == "atp=r:200;c:30"
    # Preserves original headers
    assert injected["Content-Type"] == "application/json"
    assert injected["Authorization"] == "Bearer token"


def test_inject_w3c_trace_headers_respects_existing_headers():
    explicit_tp = "00-11111111111111112222222222222222-3333333333333333-01"
    explicit_ts = "congo=t61rcWkgMzE,rojo=00f067aa0ba902b7"

    # Case 1: Exact lowercase
    headers = {"traceparent": explicit_tp, "tracestate": explicit_ts}
    res = inject_w3c_trace_headers(headers, run_id=1, case_id=2)
    assert res["traceparent"] == explicit_tp
    assert res["tracestate"] == explicit_ts

    # Case 2: Mixed-case header names
    headers_mixed = {"Traceparent": explicit_tp, "TraceState": explicit_ts}
    res_mixed = inject_w3c_trace_headers(headers_mixed, run_id=1, case_id=2)
    assert res_mixed["Traceparent"] == explicit_tp
    assert res_mixed["TraceState"] == explicit_ts
    assert "traceparent" not in res_mixed  # Not duplicated with lowercase
