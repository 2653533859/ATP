"""多协议多端工作流拓扑 DAG 引擎单测 (T1.1)"""

from __future__ import annotations

import pytest

from app.services.hybrid_workflow_dag_engine import (
    CyclicWorkflowError,
    NodeExecutionStatus,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
    clear_workflow_runs,
    execute_hybrid_workflow,
    get_workflow_run,
    list_workflow_runs,
    topological_sort_nodes,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_workflow_runs()
    yield
    clear_workflow_runs()


def test_topological_sort_and_cyclic_detection():
    # 1. 正常无环线性依赖 A -> B -> C
    node_a = WorkflowNode("a", "Node A", WorkflowNodeType.HTTP_REQUEST)
    node_b = WorkflowNode("b", "Node B", WorkflowNodeType.WEB_UI_STEP)
    node_c = WorkflowNode("c", "Node C", WorkflowNodeType.DATABASE_QUERY)

    edge_ab = WorkflowEdge("e1", "a", "b")
    edge_bc = WorkflowEdge("e2", "b", "c")

    ordered = topological_sort_nodes([node_c, node_a, node_b], [edge_ab, edge_bc])
    assert [n.node_id for n in ordered] == ["a", "b", "c"]

    # 2. 闭环依赖 A -> B -> C -> A 检测
    edge_ca = WorkflowEdge("e3", "c", "a")
    with pytest.raises(CyclicWorkflowError, match="循环依赖闭环"):
        topological_sort_nodes([node_a, node_b, node_c], [edge_ab, edge_bc, edge_ca])


def test_execute_multi_protocol_workflow_with_branching():
    # 模拟真实电商端到端测试链路:
    # 1. HTTP 创建订单
    # 2. 条件判断: 如果状态码为 200 则流向 iOS 支付, 否则流向失败报警
    # 3. iOS 客户端执行支付
    # 4. 数据库校验

    node_http = WorkflowNode(
        node_id="n_http",
        node_name="1. HTTP 创建测试商品",
        node_type=WorkflowNodeType.HTTP_REQUEST,
        config={"method": "POST", "url": "/api/v1/orders", "expected_status": 200},
    )
    node_cond = WorkflowNode(
        node_id="n_cond",
        node_name="2. 检查创建结果",
        node_type=WorkflowNodeType.CONDITION_BRANCH,
        condition_expr="True",
    )
    node_ios = WorkflowNode(
        node_id="n_ios",
        node_name="3. iOS 真机结账付款",
        node_type=WorkflowNodeType.MOBILE_IOS,
        config={"action": "tap_pay_confirm"},
    )
    node_fallback = WorkflowNode(
        node_id="n_fallback",
        node_name="3b. 异常降级分支",
        node_type=WorkflowNodeType.HTTP_REQUEST,
        config={"url": "/api/v1/alert"},
    )
    node_db = WorkflowNode(
        node_id="n_db",
        node_name="4. 数据库订单状态最终核验",
        node_type=WorkflowNodeType.DATABASE_QUERY,
        config={"db_type": "postgresql"},
    )

    nodes = [node_http, node_cond, node_ios, node_fallback, node_db]
    edges = [
        WorkflowEdge("e1", "n_http", "n_cond"),
        WorkflowEdge("e2", "n_cond", "n_ios", branch_type="true"),
        WorkflowEdge("e3", "n_cond", "n_fallback", branch_type="false"),
        WorkflowEdge("e4", "n_ios", "n_db"),
    ]

    report = execute_hybrid_workflow(
        workflow_id="wf_e2e_checkout",
        workflow_name="多端端到端电商交易测试流",
        nodes=nodes,
        edges=edges,
    )

    assert report.workflow_id == "wf_e2e_checkout"
    assert report.total_nodes == 5
    assert report.status == "SUCCESS"

    record_map = {r.node_id: r for r in report.node_records}
    assert record_map["n_http"].status == NodeExecutionStatus.SUCCESS
    assert record_map["n_cond"].status == NodeExecutionStatus.SUCCESS
    assert record_map["n_ios"].status == NodeExecutionStatus.SUCCESS
    assert record_map["n_db"].status == NodeExecutionStatus.SUCCESS
    # 降级分支节点应当被自动判定为 SKIPPED
    assert record_map["n_fallback"].status == NodeExecutionStatus.SKIPPED

    # 查验历史记录存储
    assert get_workflow_run(report.run_id) is not None
    assert len(list_workflow_runs()) == 1
