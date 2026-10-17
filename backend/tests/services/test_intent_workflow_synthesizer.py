"""自然语言意图驱动工作流合成器单测 (T1.1)"""

from __future__ import annotations

import pytest

from app.services.hybrid_workflow_dag_engine import WorkflowNodeType
from app.services.intent_workflow_synthesizer import (
    clear_synthesis_history,
    get_synthesis_result,
    list_synthesis_history,
    refine_workflow_with_intent,
    synthesize_workflow_from_intent,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_synthesis_history()
    yield
    clear_synthesis_history()


def test_synthesize_workflow_from_intent_and_variable_binding():
    prompt = (
        "首先通过 HTTP 接口创建商品订单，接着在 Web 端确认加购，然后在 iOS 真机上完成支付手势，最后在数据库核验订单状态"
    )

    dag = synthesize_workflow_from_intent(
        prompt=prompt,
        workflow_id="wf_intent_test_01",
        workflow_name="端到端多端交易流",
    )

    assert dag.workflow_id == "wf_intent_test_01"
    assert dag.workflow_name == "端到端多端交易流"
    assert len(dag.nodes) >= 4
    assert len(dag.edges) == len(dag.nodes) - 1  # 串联拓扑

    node_types = [n.node_type for n in dag.nodes]
    assert WorkflowNodeType.HTTP_REQUEST in node_types
    assert WorkflowNodeType.DATABASE_QUERY in node_types

    # 查验跨节点变量绑定
    assert len(dag.variable_bindings) >= 1
    assert any("output.body.order_id" in expr for expr in dag.variable_bindings.values())

    # 查验单条记录与历史列表
    assert get_synthesis_result(dag.synthesis_id) is not None
    assert len(list_synthesis_history()) == 1


def test_refine_workflow_with_intent():
    prompt = "HTTP 创建商品，Web 加购，iOS 支付"
    dag = synthesize_workflow_from_intent(prompt)
    original_node_count = len(dag.nodes)

    # 发起微调指令追加延时等待
    refined = refine_workflow_with_intent(
        synthesis_id=dag.synthesis_id,
        refinement_prompt="在支付后添加一个延时等待 500ms",
    )

    assert len(refined.nodes) == original_node_count + 1
    assert refined.nodes[-1].node_type == WorkflowNodeType.DELAY_SLEEP
    assert refined.nodes[-1].config.get("delay_ms") == 500
    assert len(refined.edges) == len(refined.nodes) - 1
