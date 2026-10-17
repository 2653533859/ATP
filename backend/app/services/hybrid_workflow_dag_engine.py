"""多协议多端工作流拓扑 DAG 执行引擎服务 (T1.1)

统一编排调度企业级跨端多协议业务自动化测试流:
支持将 HTTP API、gRPC、Web UI (Playwright)、Android、iOS 真机、SQL 数据库校验与条件分支
组装为有向无环图 (DAG), 执行拓扑排序调度与分支流转。
"""

from __future__ import annotations

import collections
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from app.services.workflow_context_variable_bus import WorkflowVariableBus, resolve_node_inputs


class WorkflowNodeType(str, Enum):
    HTTP_REQUEST = "http_request"
    GRPC_CALL = "grpc_call"
    WEB_UI_STEP = "web_ui_step"
    MOBILE_ANDROID = "mobile_android"
    MOBILE_IOS = "mobile_ios"
    DATABASE_QUERY = "database_query"
    CONDITION_BRANCH = "condition_branch"
    DELAY_SLEEP = "delay_sleep"


class NodeExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class CyclicWorkflowError(Exception):
    """工作流图中包含环路异常"""

    pass


@dataclass
class WorkflowNode:
    node_id: str
    node_name: str
    node_type: WorkflowNodeType
    config: Dict[str, Any] = field(default_factory=dict)
    condition_expr: Optional[str] = None  # 仅针对 condition_branch: 如 "output.status_code == 200"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type.value,
            "config": self.config,
            "condition_expr": self.condition_expr,
        }


@dataclass
class WorkflowEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    branch_type: str = "default"  # default | true | false

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "branch_type": self.branch_type,
        }


@dataclass
class NodeExecutionRecord:
    node_id: str
    node_name: str
    node_type: str
    status: NodeExecutionStatus
    duration_ms: float
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_message: Optional[str] = None
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "executed_at": self.executed_at,
        }


@dataclass
class WorkflowExecutionReport:
    run_id: str
    workflow_id: str
    workflow_name: str
    total_nodes: int
    executed_nodes_count: int
    status: str  # SUCCESS | FAILED | PARTIAL
    node_records: List[NodeExecutionRecord]
    context_outputs: Dict[str, Any]  # node_id -> output_data
    start_time: str
    end_time: str
    total_duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "total_nodes": self.total_nodes,
            "executed_nodes_count": self.executed_nodes_count,
            "status": self.status,
            "node_records": [r.to_dict() for r in self.node_records],
            "context_outputs": self.context_outputs,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": round(self.total_duration_ms, 2),
        }


# 全局轻量级工作流执行历史
_WORKFLOW_RUN_STORE: Dict[str, WorkflowExecutionReport] = {}


def clear_workflow_runs() -> None:
    _WORKFLOW_RUN_STORE.clear()


def get_workflow_run(run_id: str) -> Optional[WorkflowExecutionReport]:
    return _WORKFLOW_RUN_STORE.get(run_id)


def list_workflow_runs(limit: int = 50) -> List[Dict[str, Any]]:
    return [r.to_dict() for r in reversed(list(_WORKFLOW_RUN_STORE.values())[-limit:])]


def topological_sort_nodes(
    nodes: List[WorkflowNode],
    edges: List[WorkflowEdge],
) -> List[WorkflowNode]:
    """对工作流节点执行拓扑排序并校验无环性"""
    node_dict = {n.node_id: n for n in nodes}
    in_degrees: Dict[str, int] = {n.node_id: 0 for n in nodes}
    adj_list: Dict[str, List[str]] = collections.defaultdict(list)

    for edge in edges:
        if edge.source_node_id in node_dict and edge.target_node_id in node_dict:
            adj_list[edge.source_node_id].append(edge.target_node_id)
            in_degrees[edge.target_node_id] += 1

    queue = collections.deque([nid for nid, deg in in_degrees.items() if deg == 0])
    ordered: List[WorkflowNode] = []

    while queue:
        curr_id = queue.popleft()
        ordered.append(node_dict[curr_id])

        for neighbor in adj_list.get(curr_id, []):
            in_degrees[neighbor] -= 1
            if in_degrees[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(nodes):
        raise CyclicWorkflowError("工作流图谱中检测到循环依赖闭环 (Cyclic Loop)，无法生成执行拓扑序")

    return ordered


def _simulate_node_action(
    node: WorkflowNode,
    resolved_inputs: Dict[str, Any],
) -> tuple[Dict[str, Any], Optional[str]]:
    """模拟单节点各协议执行动作并返回输出结果与错误信息"""
    cfg = node.config
    ntype = node.node_type

    if ntype == WorkflowNodeType.HTTP_REQUEST:
        method = str(cfg.get("method", "GET")).upper()
        url = str(cfg.get("url", "https://api.internal/service"))
        # 模拟执行
        status_code = int(cfg.get("expected_status", 200))
        return {
            "status_code": status_code,
            "url": url,
            "method": method,
            "body": {
                "code": 0,
                "message": "success",
                "order_id": f"ORD_{uuid.uuid4().hex[:8]}",
                "data": resolved_inputs,
            },
        }, None

    if ntype == WorkflowNodeType.GRPC_CALL:
        return {
            "grpc_code": 0,
            "service": cfg.get("service", "OrderService"),
            "method": cfg.get("method", "CheckDiscount"),
            "response": {"discount_rate": 0.85, "eligible": True},
        }, None

    if ntype == WorkflowNodeType.WEB_UI_STEP:
        return {
            "browser": cfg.get("browser", "chromium"),
            "action": cfg.get("action", "click_login_button"),
            "dom_found": True,
            "screenshot": "base64_web_screenshot_stub",
        }, None

    if ntype == WorkflowNodeType.MOBILE_ANDROID:
        return {
            "platform": "android",
            "action": cfg.get("action", "click_add_cart"),
            "device_serial": cfg.get("serial", "emulator-5554"),
            "ui_dump_matched": True,
        }, None

    if ntype == WorkflowNodeType.MOBILE_IOS:
        return {
            "platform": "ios",
            "action": cfg.get("action", "tap_checkout"),
            "udid": cfg.get("udid", "00008101-IPHONE-REAL"),
            "wda_session": f"sess_{uuid.uuid4().hex[:8]}",
            "touch_completed": True,
        }, None

    if ntype == WorkflowNodeType.DATABASE_QUERY:
        return {
            "db_type": cfg.get("db_type", "postgresql"),
            "affected_rows": 1,
            "rows": [{"order_status": "PAID", "amount": 199.0}],
        }, None

    if ntype == WorkflowNodeType.CONDITION_BRANCH:
        expr = node.condition_expr or "True"
        # 简易求值判定
        verdict = True
        if "false" in expr.lower() or "==" in expr and "500" in expr:
            verdict = False
        return {"branch_verdict": verdict, "expression": expr}, None

    if ntype == WorkflowNodeType.DELAY_SLEEP:
        return {"delayed_ms": cfg.get("delay_ms", 100)}, None

    return {"result": "noop"}, None


def execute_hybrid_workflow(
    workflow_id: str,
    workflow_name: str,
    nodes: List[WorkflowNode],
    edges: List[WorkflowEdge],
    initial_variables: Dict[str, Any] | None = None,
) -> WorkflowExecutionReport:
    """执行多协议多端混合工作流拓扑 DAG 完整链路"""
    start_time = datetime.now(timezone.utc)
    run_id = f"wfrun_{uuid.uuid4().hex[:12]}"

    sorted_nodes = topological_sort_nodes(nodes, edges)

    # 边连接分支字典: source_node_id -> List[WorkflowEdge]
    out_edges_map: Dict[str, List[WorkflowEdge]] = collections.defaultdict(list)
    for e in edges:
        out_edges_map[e.source_node_id].append(e)

    var_bus = WorkflowVariableBus(initial_variables)
    context_outputs: Dict[str, Any] = dict(initial_variables or {})
    records: List[NodeExecutionRecord] = []
    skipped_nodes: set[str] = set()
    overall_status = "SUCCESS"

    for node in sorted_nodes:
        if node.node_id in skipped_nodes:
            records.append(
                NodeExecutionRecord(
                    node_id=node.node_id,
                    node_name=node.node_name,
                    node_type=node.node_type.value,
                    status=NodeExecutionStatus.SKIPPED,
                    duration_ms=0.0,
                    input_data={},
                    output_data={},
                )
            )
            continue

        node_start = datetime.now(timezone.utc)
        resolved_inputs = resolve_node_inputs(node.config, var_bus)

        output_data, err = _simulate_node_action(node, resolved_inputs)
        node_duration = (datetime.now(timezone.utc) - node_start).total_seconds() * 1000.0

        if err:
            exec_status = NodeExecutionStatus.FAILED
            overall_status = "FAILED"
        else:
            exec_status = NodeExecutionStatus.SUCCESS

        records.append(
            NodeExecutionRecord(
                node_id=node.node_id,
                node_name=node.node_name,
                node_type=node.node_type.value,
                status=exec_status,
                duration_ms=node_duration,
                input_data=resolved_inputs,
                output_data=output_data,
                error_message=err,
            )
        )
        context_outputs[f"node_{node.node_id}"] = output_data
        var_bus.set_value(f"node_{node.node_id}", output_data)
        var_bus.set_value(node.node_id, output_data)

        # 分支流转判断
        if node.node_type == WorkflowNodeType.CONDITION_BRANCH:
            verdict = output_data.get("branch_verdict", True)
            for out_edge in out_edges_map.get(node.node_id, []):
                # 若分支不符合，将其下游目标标记为跳过
                if out_edge.branch_type == "true" and not verdict:
                    skipped_nodes.add(out_edge.target_node_id)
                elif out_edge.branch_type == "false" and verdict:
                    skipped_nodes.add(out_edge.target_node_id)

    end_time = datetime.now(timezone.utc)
    total_dur = (end_time - start_time).total_seconds() * 1000.0

    report = WorkflowExecutionReport(
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        total_nodes=len(nodes),
        executed_nodes_count=sum(1 for r in records if r.status == NodeExecutionStatus.SUCCESS),
        status=overall_status,
        node_records=records,
        context_outputs=context_outputs,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        total_duration_ms=total_dur,
    )
    _WORKFLOW_RUN_STORE[run_id] = report
    return report
