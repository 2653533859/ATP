"""拓扑中断级联跳过与孤立节点容错控制器单测 (T2.3)"""

from __future__ import annotations

from app.services.case_dag_dependency_builder import CaseDAGBuilder
from app.services.dag_cascade_fault_controller import (
    DAGCascadeFaultController,
    NodeExecutionStatus,
)
from app.services.dag_wave_execution_dispatcher import (
    WaveDispatchNode,
    plan_dag_execution_waves,
)


def test_cascade_failure_skips_downstream_subtree():
    builder = CaseDAGBuilder()

    # 链路 1: A (登录) -> B (建单) -> C (支付)
    builder.add_case("case_login", "登录", produces=["token"], metadata={"cost_seconds": 10.0})
    builder.add_case("case_order", "建单", consumes=["token"], produces=["oid"], metadata={"cost_seconds": 15.0})
    builder.add_case("case_pay", "支付", consumes=["oid"], metadata={"cost_seconds": 20.0})

    # 链路 2: D (独立商品查询，无依赖)
    builder.add_case("case_search_product", "商品浏览查询", metadata={"cost_seconds": 5.0})

    dag = builder.build_dag()
    plan = plan_dag_execution_waves(dag)

    controller = DAGCascadeFaultController(dag, plan)

    # 1. 验证下游可达遍历
    downstream_a = controller.get_all_downstream_reachable("case_login")
    assert downstream_a == {"case_order", "case_pay"}

    # 2. 模拟 case_login 执行失败
    records = controller.register_node_failure("case_login", error_message="账号密码认证失败 401")
    assert len(records) == 3  # failed + 2 cascade skipped
    assert controller.node_states["case_login"] == NodeExecutionStatus.FAILED
    assert controller.node_states["case_order"] == NodeExecutionStatus.CASCADE_SKIPPED
    assert controller.node_states["case_pay"] == NodeExecutionStatus.CASCADE_SKIPPED

    # 查验根因记录
    assert controller.fault_root_causes["case_login"] == ["case_order", "case_pay"]

    # 3. 验证波次节点过滤: Wave 1 中的 case_order 已经被过滤跳过
    wave_1_nodes = [
        WaveDispatchNode(case_id="case_order", case_name="建单"),
    ]
    schedulable = controller.filter_schedulable_nodes(wave_1_nodes)
    assert len(schedulable) == 0

    # 4. 验证独立孤立节点不受影响，成功执行
    controller.register_node_success("case_search_product")
    assert controller.node_states["case_search_product"] == NodeExecutionStatus.SUCCESS

    # 5. 生成完整容错报告
    rep = controller.generate_fault_report()
    assert rep.total_cases_count == 4
    assert rep.success_count == 1
    assert rep.failed_count == 1
    assert rep.cascade_skipped_count == 2
    assert rep.isolated_success_count == 1
    assert rep.saved_execution_time_seconds == 35.0  # 15s + 20s

    d = rep.to_dict()
    assert d["cascade_skipped_count"] == 2
    assert d["isolated_success_count"] == 1
    assert d["saved_execution_time_seconds"] == 35.0
