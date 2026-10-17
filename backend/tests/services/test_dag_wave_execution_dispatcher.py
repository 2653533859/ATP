"""基于拓扑排序的并发波次分发与前置状态传递器单测 (T2.2)"""

from __future__ import annotations

from app.services.case_dag_dependency_builder import CaseDAGBuilder
from app.services.dag_wave_execution_dispatcher import (
    plan_dag_execution_waves,
    simulate_wave_pipeline_execution,
)


def test_plan_dag_execution_waves_concurrency():
    builder = CaseDAGBuilder()

    # Wave 0 节点 (入度为 0): 登录 与 初始化配置
    builder.add_case(
        case_id="case_login",
        case_name="登录主用例",
        produces=["auth_token"],
        metadata={"cost_seconds": 10.0},
    )
    builder.add_case(
        case_id="case_init_config",
        case_name="系统配置拉取",
        produces=["app_config"],
        metadata={"cost_seconds": 8.0},
    )

    # Wave 1 节点: 创建订单 (消费 auth_token)
    builder.add_case(
        case_id="case_create_order",
        case_name="创建订单",
        consumes=["auth_token"],
        produces=["order_id"],
        metadata={"cost_seconds": 12.0},
    )

    # Wave 2 节点: 支付订单 (依赖创建订单，并消费 app_config)
    builder.add_case(
        case_id="case_pay_order",
        case_name="支付订单",
        depends_on=["case_create_order"],
        consumes=["app_config"],
        produces=["pay_receipt"],
        metadata={"cost_seconds": 15.0},
    )

    dag = builder.build_dag()
    assert dag.is_valid_dag is True

    plan = plan_dag_execution_waves(dag)

    assert plan.total_waves_count == 3
    assert plan.total_cases_count == 4

    # Wave 0: 并发度 2 (case_init_config, case_login)
    w0 = plan.waves[0]
    assert w0.wave_index == 0
    assert w0.concurrency_level == 2
    assert sorted([n.case_id for n in w0.nodes]) == ["case_init_config", "case_login"]
    assert w0.wave_estimated_duration_seconds == 10.0  # max(10, 8)

    # Wave 1: 并发度 1 (case_create_order)
    w1 = plan.waves[1]
    assert w1.wave_index == 1
    assert w1.concurrency_level == 1
    assert w1.nodes[0].case_id == "case_create_order"

    # Wave 2: 终止波次 (case_pay_order)
    w2 = plan.waves[2]
    assert w2.wave_index == 2
    assert w2.is_terminal is True
    assert w2.nodes[0].case_id == "case_pay_order"

    # 关键路径耗时: 10 + 12 + 15 = 37s，串行耗时: 10 + 8 + 12 + 15 = 45s
    assert plan.critical_path_duration_seconds == 37.0
    assert plan.sequential_duration_seconds == 45.0
    assert plan.concurrency_acceleration_ratio > 1.0


def test_simulate_wave_pipeline_execution():
    builder = CaseDAGBuilder()
    builder.add_case("case_auth", "获取Token", produces=["token"])
    builder.add_case("case_fetch", "读取数据", consumes=["token"], produces=["user_data"])
    dag = builder.build_dag()

    plan = plan_dag_execution_waves(dag)
    sim_res = simulate_wave_pipeline_execution(plan, initial_context={"env": "staging"})

    assert sim_res["total_waves_dispatched"] == 2
    assert "token" in sim_res["final_pipeline_variables"]
    assert "user_data" in sim_res["final_pipeline_variables"]
    assert sim_res["final_pipeline_variables"]["env"] == "staging"

    # 查验第二波次用例收到了前置注入的 token
    w1_node = sim_res["wave_executions"][1]["nodes"][0]
    assert w1_node["case_id"] == "case_fetch"
    assert "token" in w1_node["injected_variables"]


def test_empty_dag_plan():
    builder = CaseDAGBuilder()
    dag = builder.build_dag()
    plan = plan_dag_execution_waves(dag)
    assert plan.total_waves_count == 0
    assert plan.concurrency_acceleration_ratio == 1.0

    d = plan.to_dict()
    assert d["plan_id"].startswith("wplan_")
    assert d["total_waves_count"] == 0
