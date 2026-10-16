"""自主探索式 API 模糊变异与隐蔽缺陷深度探查单元测试 (T3.3)。"""

from __future__ import annotations

import pytest
from app.services.autonomous_api_fuzzing_explorer import (
    FuzzFlawType,
    FuzzMutationStrategy,
    clear_fuzzing_store,
    execute_fuzzing_exploration,
    get_fuzzing_session,
    list_fuzzing_sessions,
)


@pytest.fixture(autouse=True)
def _reset_fuzzing_state():
    clear_fuzzing_store()
    yield
    clear_fuzzing_store()


def test_execute_fuzzing_exploration_detect_crash_and_dos():
    """测试模糊变异探测出 500 异常崩溃、SQL 报错以及耗时尖刺。"""
    session = execute_fuzzing_exploration(
        endpoint="/api/v1/orders/pay",
        method="POST",
        base_payload={"order_no": "ORD10001", "notes": "normal"},
    )

    assert session.target_endpoint == "/api/v1/orders/pay"
    assert session.total_mutations_count > 0
    assert session.flaws_count > 0
    assert session.critical_count > 0

    # 验证缺陷分类
    flaw_types = {f.flaw_type for f in session.findings}
    assert FuzzFlawType.UNHANDLED_SERVER_CRASH in flaw_types

    # 验证 cURL 复现命令存在
    for f in session.findings:
        assert "curl -X POST '/api/v1/orders/pay'" in f.reproduction_curl

    # 验证持久化
    saved = get_fuzzing_session(session.session_id)
    assert saved is not None
    assert saved.session_id == session.session_id


def test_execute_fuzzing_specific_strategies():
    """测试指定单一策略 (XSS_HTML_PAYLOAD)。"""
    session = execute_fuzzing_exploration(
        endpoint="/api/v1/comments",
        method="POST",
        base_payload={"content": "hello"},
        strategies=[FuzzMutationStrategy.XSS_HTML_PAYLOAD.value],
    )

    assert session.total_mutations_count == 3  # XSS 有 3 个向量
    assert len(list_fuzzing_sessions()) == 1


def test_clear_fuzzing_sessions():
    """测试清空会话记录。"""
    execute_fuzzing_exploration(endpoint="/api/v1/test")
    assert len(list_fuzzing_sessions()) == 1

    clear_fuzzing_store()
    assert len(list_fuzzing_sessions()) == 0
