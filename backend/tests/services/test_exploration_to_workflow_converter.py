"""探索轨迹逆向工作流转换器单测 (T2.3)"""

from __future__ import annotations

from app.services.exploration_to_workflow_converter import convert_exploration_to_workflow
from app.services.vlm_autonomous_explorer import (
    ExplorationActionType,
    ExplorationSession,
    StateTransitionEdge,
)


def test_convert_exploration_session_to_workflow_draft():
    sess = ExplorationSession(
        session_id="expsess_test_001",
        platform="ios",
        device_id="00008101-IPHONE-REAL-99",
        goal="探索 iOS 客户端登录与加购",
        status="COMPLETED",
        transitions=[
            StateTransitionEdge(
                transition_id="t1",
                from_state_id="s1",
                to_state_id="s2",
                action_type=ExplorationActionType.TAP,
                target_element_label="首页登录按钮",
            ),
            StateTransitionEdge(
                transition_id="t2",
                from_state_id="s2",
                to_state_id="s3",
                action_type=ExplorationActionType.INPUT,
                target_element_label="账号输入框",
            ),
        ],
    )

    draft = convert_exploration_to_workflow(sess)
    assert draft["workflow_id"].startswith("wf_from_exp_")
    assert "登录与加购" in draft["workflow_name"]

    # 1. 前置初始化节点 + 2 个探索动作节点 = 3 个节点
    nodes = draft["nodes"]
    assert len(nodes) == 3
    assert nodes[0]["node_type"] == "mobile_ios"
    assert "初始化并连接 iOS 真机" in nodes[0]["node_name"]

    # 2. 边连接
    edges = draft["edges"]
    assert len(edges) == 2
    assert edges[0]["source_node_id"] == "node_1"
    assert edges[0]["target_node_id"] == "node_2"
    assert edges[1]["source_node_id"] == "node_2"
    assert edges[1]["target_node_id"] == "node_3"
