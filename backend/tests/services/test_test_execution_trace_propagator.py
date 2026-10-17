"""测试执行链路上下文传播拦截器服务单测 (T1.2)"""

from __future__ import annotations

from app.services.test_execution_trace_propagator import (
    bind_execution_trace,
    clear_execution_trace_sessions,
    get_execution_trace_session,
    list_execution_trace_sessions,
    pack_celery_task_headers,
    propagate_step_trace,
    unpack_celery_task_headers,
)


def test_execution_trace_session_lifecycle():
    clear_execution_trace_sessions()

    # 1. 绑定初始会话
    session = bind_execution_trace(
        run_id="run_1001",
        case_id="case_login",
        carrier_type="celery_async",
        metadata={"user": "tester", "env": "staging"},
    )
    assert session.run_id == "run_1001"
    assert session.case_id == "case_login"
    assert len(session.root_trace_context.trace_id) == 32
    assert session.root_trace_context.sampled is True
    assert "run_id=run_1001" in session.root_trace_context.tracestate

    # 2. 多步骤链式传播（TraceID 必须保持一致，SpanID 衍生）
    step1 = propagate_step_trace(
        run_id="run_1001",
        step_index=1,
        step_name="发送短信验证码",
        request_headers={"User-Agent": "ATP-TestAgent/1.0"},
    )
    assert step1.step_index == 1
    assert "traceparent" in step1.injected_headers
    step1_tp = step1.injected_headers["traceparent"]
    assert session.root_trace_context.trace_id in step1_tp
    assert step1.parent_span_id == session.root_trace_context.span_id
    assert "step=1" in step1.injected_headers["tracestate"]

    step2 = propagate_step_trace(
        run_id="run_1001",
        step_index=2,
        step_name="校验验证码并登录",
        request_headers={"Authorization": "Bearer tmp_token"},
    )
    assert step2.step_index == 2
    step2_tp = step2.injected_headers["traceparent"]
    assert session.root_trace_context.trace_id in step2_tp  # 仍是同一 TraceID
    assert step2.step_span_id != step1.step_span_id  # 步骤 SpanID 独立

    # 3. 查验会话完整 Trail
    queried = get_execution_trace_session("run_1001")
    assert queried is not None
    assert len(queried.steps) == 2
    sessions = list_execution_trace_sessions(limit=10)
    assert len(sessions) == 1
    assert sessions[0]["steps_count"] == 2


def test_celery_task_headers_pack_and_unpack():
    clear_execution_trace_sessions()

    # 原生上游发起
    bind_execution_trace(run_id="run_2002", case_id="case_checkout")
    packed_headers = pack_celery_task_headers("run_2002")
    assert "traceparent" in packed_headers
    assert packed_headers["x_atp_run_id"] == "run_2002"
    assert packed_headers["x_atp_case_id"] == "case_checkout"

    # Worker 接收侧解包并成功恢复会话
    recovered = unpack_celery_task_headers(packed_headers)
    assert recovered is not None
    assert recovered.run_id == "run_2002"
    # 派生子 Span，但维持一致的 TraceID
    assert recovered.carrier_type == "celery_worker_receiver"
