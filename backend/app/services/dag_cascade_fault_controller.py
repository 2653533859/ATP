"""拓扑中断级联跳过与孤立节点容错控制器服务 (T2.3)

在 DAG 波次调度执行中提供前置依赖失败级联跳过与无依赖孤立节点安全容错调度机制:
1. 用例节点执行状态机 (NodeExecutionStatus: PENDING | SUCCESS | FAILED | CASCADE_SKIPPED);
2. 前置节点失败时下游依赖子图深度遍历与智能级联跳过 (Cascade Fault Propagation);
3. 孤立节点与并行分支故障隔离，防止雪崩式误报假失败 (Fault Isolation);
4. 结构化容错执行报告与节省无效开销统计 (CascadeFaultExecutionReport)。
"""

from __future__ import annotations

import collections
import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.case_dag_dependency_builder import CaseDAGGraphResult
from app.services.dag_wave_execution_dispatcher import DAGWavePlanResult, WaveDispatchNode


class NodeExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"  # 待调度
    RUNNING = "RUNNING"  # 正在执行
    SUCCESS = "SUCCESS"  # 执行成功
    FAILED = "FAILED"  # 执行失败
    CASCADE_SKIPPED = "CASCADE_SKIPPED"  # 前置依赖失败，智能级联跳过


@dataclass
class NodeExecutionRecord:
    case_id: str
    case_name: str
    status: NodeExecutionStatus
    wave_index: int
    error_message: Optional[str] = None
    cascade_skip_reason: Optional[str] = None
    saved_time_seconds: float = 0.0
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class CascadeFaultExecutionReport:
    report_id: str
    plan_id: str
    dag_id: str
    total_cases_count: int
    success_count: int
    failed_count: int
    cascade_skipped_count: int
    isolated_success_count: int
    saved_execution_time_seconds: float
    fault_root_causes: Dict[str, List[str]]  # root_failed_case_id -> list of skipped downstream case_ids
    node_records: List[NodeExecutionRecord]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "plan_id": self.plan_id,
            "dag_id": self.dag_id,
            "total_cases_count": self.total_cases_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "cascade_skipped_count": self.cascade_skipped_count,
            "isolated_success_count": self.isolated_success_count,
            "saved_execution_time_seconds": round(self.saved_execution_time_seconds, 1),
            "fault_root_causes": self.fault_root_causes,
            "node_records": [r.to_dict() for r in self.node_records],
            "generated_at": self.generated_at,
        }


class DAGCascadeFaultController:
    """DAG 拓扑级联故障与容错控制器"""

    def __init__(self, dag: CaseDAGGraphResult, plan: Optional[DAGWavePlanResult] = None):
        self.dag = dag
        self.plan = plan
        self.node_states: Dict[str, NodeExecutionStatus] = {cid: NodeExecutionStatus.PENDING for cid in dag.nodes}
        self.records: Dict[str, NodeExecutionRecord] = {}
        self.fault_root_causes: Dict[str, List[str]] = collections.defaultdict(list)

        # 预构建下游邻接表
        self.downstream_adj: Dict[str, Set[str]] = collections.defaultdict(set)
        for cid, node in dag.nodes.items():
            self.downstream_adj[cid] = set(node.downstream_case_ids)

    def _get_case_wave_index(self, case_id: str) -> int:
        if not self.plan:
            return 0
        for w in self.plan.waves:
            if any(n.case_id == case_id for n in w.nodes):
                return w.wave_index
        return 0

    def get_all_downstream_reachable(self, case_id: str) -> Set[str]:
        """BFS 遍历获取该节点的所有下游直接与间接依赖节点"""
        visited: Set[str] = set()
        queue = collections.deque(self.downstream_adj.get(case_id, set()))
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(self.downstream_adj.get(curr, set()))
        return visited

    def register_node_success(self, case_id: str) -> NodeExecutionRecord:
        """登记节点执行成功"""
        self.node_states[case_id] = NodeExecutionStatus.SUCCESS
        node_data = self.dag.nodes.get(case_id)
        name = node_data.case_name if node_data else case_id

        rec = NodeExecutionRecord(
            case_id=case_id,
            case_name=name,
            status=NodeExecutionStatus.SUCCESS,
            wave_index=self._get_case_wave_index(case_id),
        )
        self.records[case_id] = rec
        return rec

    def register_node_failure(
        self,
        case_id: str,
        error_message: str = "用例步骤执行断言失败或超时",
    ) -> List[NodeExecutionRecord]:
        """登记节点执行失败，并自动级联跳过所有下游依赖子节点"""
        self.node_states[case_id] = NodeExecutionStatus.FAILED
        node_data = self.dag.nodes.get(case_id)
        name = node_data.case_name if node_data else case_id

        failed_rec = NodeExecutionRecord(
            case_id=case_id,
            case_name=name,
            status=NodeExecutionStatus.FAILED,
            wave_index=self._get_case_wave_index(case_id),
            error_message=error_message,
        )
        self.records[case_id] = failed_rec

        # 级联扩散跳过下游节点
        impacted_downstream = self.get_all_downstream_reachable(case_id)
        cascade_records: List[NodeExecutionRecord] = [failed_rec]

        for down_id in sorted(impacted_downstream):
            # 仅处理尚未执行完成的 PENDING 节点
            if self.node_states.get(down_id) in (NodeExecutionStatus.PENDING, None):
                self.node_states[down_id] = NodeExecutionStatus.CASCADE_SKIPPED
                self.fault_root_causes[case_id].append(down_id)

                down_node = self.dag.nodes.get(down_id)
                down_name = down_node.case_name if down_node else down_id
                saved_cost = float(down_node.metadata.get("cost_seconds", 10.0)) if down_node else 10.0

                skip_rec = NodeExecutionRecord(
                    case_id=down_id,
                    case_name=down_name,
                    status=NodeExecutionStatus.CASCADE_SKIPPED,
                    wave_index=self._get_case_wave_index(down_id),
                    cascade_skip_reason=f"前置依赖用例 [{name} ({case_id})] 执行失败，阻断下游级联假失败",
                    saved_time_seconds=saved_cost,
                )
                self.records[down_id] = skip_rec
                cascade_records.append(skip_rec)

        return cascade_records

    def filter_schedulable_nodes(self, wave_nodes: List[WaveDispatchNode]) -> List[WaveDispatchNode]:
        """过滤波次中已被级联跳过的节点，仅返回真正允许调度的有效节点"""
        return [node for node in wave_nodes if self.node_states.get(node.case_id) == NodeExecutionStatus.PENDING]

    def generate_fault_report(self) -> CascadeFaultExecutionReport:
        """生成完整的级联容错执行统计报告"""
        report_id = f"crep_{uuid.uuid4().hex[:10]}"
        plan_id = self.plan.plan_id if self.plan else "direct_dag_run"

        success_count = sum(1 for s in self.node_states.values() if s == NodeExecutionStatus.SUCCESS)
        failed_count = sum(1 for s in self.node_states.values() if s == NodeExecutionStatus.FAILED)
        skipped_count = sum(1 for s in self.node_states.values() if s == NodeExecutionStatus.CASCADE_SKIPPED)

        saved_seconds = sum(
            r.saved_time_seconds for r in self.records.values() if r.status == NodeExecutionStatus.CASCADE_SKIPPED
        )

        # 统计在存在前置故障下，依然正常成功执行的无依赖孤立节点数
        isolated_success = 0
        if failed_count > 0:
            for cid, s in self.node_states.items():
                if s == NodeExecutionStatus.SUCCESS:
                    node = self.dag.nodes.get(cid)
                    # 无上游依赖或者其上游全部不在失败链上的节点
                    if node and len(node.upstream_case_ids) == 0:
                        isolated_success += 1

        return CascadeFaultExecutionReport(
            report_id=report_id,
            plan_id=plan_id,
            dag_id=self.dag.dag_id,
            total_cases_count=self.dag.nodes_count,
            success_count=success_count,
            failed_count=failed_count,
            cascade_skipped_count=skipped_count,
            isolated_success_count=isolated_success,
            saved_execution_time_seconds=saved_seconds,
            fault_root_causes=dict(self.fault_root_causes),
            node_records=list(self.records.values()),
        )
