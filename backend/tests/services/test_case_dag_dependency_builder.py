"""用例数据上下文有向无环图构建与环路检测器单测 (T2.1)"""

from __future__ import annotations

from app.services.case_dag_dependency_builder import (
    CaseDAGBuilder,
    DependencyType,
)


def test_build_explicit_and_data_flow_dag():
    builder = CaseDAGBuilder()

    # 1. 用例 A: 登录，生产 token
    builder.add_case(
        case_id="case_login",
        case_name="用户登录",
        produces=["auth_token"],
    )

    # 2. 用例 B: 创建订单，消费 token，生产 order_id
    builder.add_case(
        case_id="case_create_order",
        case_name="创建订单",
        consumes=["auth_token"],
        produces=["order_id"],
    )

    # 3. 用例 C: 支付，显式依赖创建订单，并消费 order_id
    builder.add_case(
        case_id="case_pay_order",
        case_name="支付订单",
        depends_on=["case_create_order"],
        consumes=["order_id"],
    )

    dag = builder.build_dag()

    assert dag.is_valid_dag is True
    assert dag.nodes_count == 3
    assert len(dag.cycles) == 0

    # 检查根节点与叶子节点
    assert dag.root_case_ids == ["case_login"]
    assert dag.leaf_case_ids == ["case_pay_order"]

    # 检查边关系
    edge_login_to_order = next(
        e for e in dag.edges if e.source_case_id == "case_login" and e.target_case_id == "case_create_order"
    )
    assert edge_login_to_order.dependency_type == DependencyType.DATA_VARIABLE_FLOW
    assert "auth_token" in edge_login_to_order.shared_variables

    edge_order_to_pay = next(
        e for e in dag.edges if e.source_case_id == "case_create_order" and e.target_case_id == "case_pay_order"
    )
    assert edge_order_to_pay.dependency_type == DependencyType.EXPLICIT_PREREQUISITE


def test_tarjan_cycle_detection():
    builder = CaseDAGBuilder()

    # 构造三节点循环死锁: A -> B -> C -> A
    builder.add_case(case_id="case_a", case_name="节点A", depends_on=["case_c"])
    builder.add_case(case_id="case_b", case_name="节点B", depends_on=["case_a"])
    builder.add_case(case_id="case_c", case_name="节点C", depends_on=["case_b"])

    dag = builder.build_dag()

    assert dag.is_valid_dag is False
    assert len(dag.cycles) > 0
    cycle_nodes = set(dag.cycles[0])
    assert cycle_nodes == {"case_a", "case_b", "case_c"}


def test_independent_isolated_cases():
    builder = CaseDAGBuilder()
    builder.add_case(case_id="case_iso_1", case_name="独立测试1")
    builder.add_case(case_id="case_iso_2", case_name="独立测试2")

    dag = builder.build_dag()
    assert dag.is_valid_dag is True
    assert dag.edges_count == 0
    assert sorted(dag.root_case_ids) == ["case_iso_1", "case_iso_2"]
    assert sorted(dag.leaf_case_ids) == ["case_iso_1", "case_iso_2"]

    d = dag.to_dict()
    assert d["nodes_count"] == 2
    assert d["is_valid_dag"] is True
