"""W3C TraceContext 标准注入器服务单测 (T1.1)"""

from __future__ import annotations


from app.services.w3c_trace_context_injector import (
    clear_injected_trace_store,
    create_child_span_context,
    create_trace_context,
    extract_trace_context,
    generate_span_id,
    generate_trace_id,
    inject_trace_context,
    list_injected_trace_contexts,
    validate_traceparent,
    INVALID_SPAN_ID,
    INVALID_TRACE_ID,
)


def test_w3c_trace_generation_and_validation():
    tid = generate_trace_id()
    assert len(tid) == 32
    assert tid != INVALID_TRACE_ID

    sid = generate_span_id()
    assert len(sid) == 16
    assert sid != INVALID_SPAN_ID

    valid_tp = f"00-{tid}-{sid}-01"
    assert validate_traceparent(valid_tp) is True

    # 测试非法格式
    assert validate_traceparent("") is False
    assert validate_traceparent("invalid") is False
    assert validate_traceparent(f"01-{tid}-{sid}-01") is False  # 非 00 version
    assert validate_traceparent(f"00-{INVALID_TRACE_ID}-{sid}-01") is False  # 全 0 trace_id
    assert validate_traceparent(f"00-{tid}-{INVALID_SPAN_ID}-01") is False  # 全 0 span_id


def test_w3c_trace_injection_and_extraction():
    clear_injected_trace_store()

    ctx = create_trace_context(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        sampled=True,
        tracestate="atp=c:stress;s:1,rojo=1",
    )
    assert ctx.traceparent == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert ctx.trace_flags == "01"

    headers = {"Content-Type": "application/json"}
    injected = inject_trace_context(headers, context=ctx, carrier_type="http")

    assert "traceparent" in injected
    assert injected["traceparent"] == ctx.traceparent
    assert injected["tracestate"] == "atp=c:stress;s:1,rojo=1"

    # 大小写不敏感提取
    upper_headers = {
        "TRACEPARENT": ctx.traceparent,
        "TRACESTATE": "atp=c:stress;s:1,rojo=1",
    }
    extracted = extract_trace_context(upper_headers)
    assert extracted is not None
    assert extracted.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert extracted.span_id == "00f067aa0ba902b7"
    assert extracted.sampled is True
    assert extracted.tracestate == "atp=c:stress;s:1,rojo=1"


def test_w3c_child_span_derivation():
    clear_injected_trace_store()

    parent = create_trace_context(
        trace_id="11112222333344445555666677778888",
        span_id="aaaabbbbccccdddd",
        sampled=True,
        tracestate="origin=test",
    )

    child = create_child_span_context(
        parent_context=parent,
        new_span_id="eeeeffff00001111",
        new_tracestate_tag="step=login",
    )

    assert child.trace_id == parent.trace_id  # TraceID 不变
    assert child.parent_span_id == parent.span_id  # parent_span_id 设为父 SpanID
    assert child.span_id == "eeeeffff00001111"  # 全新 SpanID
    assert "step=login" in child.tracestate
    assert "origin=test" in child.tracestate

    history = list_injected_trace_contexts(limit=10)
    assert len(history) == 2
