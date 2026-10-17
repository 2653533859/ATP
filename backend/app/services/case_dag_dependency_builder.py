"""用例数据上下文有向无环图构建与环路检测器服务 (T2.1)

解析测试用例显式/隐式数据上下文流转依赖，构建 DAG 图谱并执行 Tarjan 算法环路死锁检测:
1. 显式前置依赖 (EXPLICIT) 与隐式变量数据流依赖 (DATA_FLOW) 智能构图;
2. 用例节点 (CaseDAGNode) 与依赖边 (CaseDAGEdge) 数据拓扑建模;
3. Tarjan 强连通分量与环路死锁探测算法 (detect_cycles_tarjan);
4. 拓扑图谱校验与结构化报告输出 (CaseDAGGraphResult)。
"""

from __future__ import annotations

import collections
import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class DependencyType(str, enum.Enum):
    EXPLICIT_PREREQUISITE = "EXPLICIT_PREREQUISITE"  # 显式声明前置依赖 (depends_on)
    DATA_VARIABLE_FLOW = "DATA_VARIABLE_FLOW"  # 变量生产-消费数据流隐式依赖


@dataclass
class CaseDAGEdge:
    edge_id: str
    source_case_id: str  # 上游前置用例
    target_case_id: str  # 下游等待用例
    dependency_type: DependencyType
    shared_variables: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dependency_type"] = self.dependency_type.value
        return d


@dataclass
class CaseDAGNode:
    case_id: str
    case_name: str
    produced_variables: List[str] = field(default_factory=list)
    consumed_variables: List[str] = field(default_factory=list)
    upstream_case_ids: Set[str] = field(default_factory=set)
    downstream_case_ids: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "produced_variables": self.produced_variables,
            "consumed_variables": self.consumed_variables,
            "upstream_case_ids": sorted(list(self.upstream_case_ids)),
            "downstream_case_ids": sorted(list(self.downstream_case_ids)),
            "metadata": self.metadata,
        }


@dataclass
class CaseDAGGraphResult:
    dag_id: str
    is_valid_dag: bool  # 是否为合法无环图
    nodes_count: int
    edges_count: int
    cycles: List[List[str]]  # 侦测到的死锁环路
    nodes: Dict[str, CaseDAGNode]
    edges: List[CaseDAGEdge]
    root_case_ids: List[str]  # 零入度根用例
    leaf_case_ids: List[str]  # 零出度末梢用例
    built_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dag_id": self.dag_id,
            "is_valid_dag": self.is_valid_dag,
            "nodes_count": self.nodes_count,
            "edges_count": self.edges_count,
            "cycles": self.cycles,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "root_case_ids": self.root_case_ids,
            "leaf_case_ids": self.leaf_case_ids,
            "built_at": self.built_at,
        }


def detect_cycles_tarjan(adj_list: Dict[str, Set[str]]) -> List[List[str]]:
    """使用 Tarjan 算法检测有向图中的强连通分量 (SCC)，识别死锁环路"""
    index = 0
    stack: List[str] = []
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    on_stack: Set[str] = set()
    sccs: List[List[str]] = []

    def _strongconnect(v: str):
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj_list.get(v, set()):
            if w not in indices:
                _strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            # 节点数大于 1，或自环
            if len(scc) > 1 or v in adj_list.get(v, set()):
                sccs.append(scc[::-1])

    for node in adj_list:
        if node not in indices:
            _strongconnect(node)

    return sccs


class CaseDAGBuilder:
    """用例依赖 DAG 构建器"""

    def __init__(self):
        self.raw_cases: List[Dict[str, Any]] = []

    def add_case(
        self,
        case_id: str,
        case_name: str,
        depends_on: Optional[List[str]] = None,
        produces: Optional[List[str]] = None,
        consumes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CaseDAGBuilder:
        """添加待编排的测试用例元数据"""
        self.raw_cases.append(
            {
                "case_id": case_id,
                "case_name": case_name,
                "depends_on": depends_on or [],
                "produces": produces or [],
                "consumes": consumes or [],
                "metadata": metadata or {},
            }
        )
        return self

    def build_dag(self) -> CaseDAGGraphResult:
        """解析显隐式依赖，构建完整 DAG 并执行死锁与环路检测"""
        dag_id = f"dag_{uuid.uuid4().hex[:10]}"
        nodes: Dict[str, CaseDAGNode] = {}
        edges: List[CaseDAGEdge] = []
        adj_list: Dict[str, Set[str]] = collections.defaultdict(set)

        # 变量生产映射: var_name -> producer_case_id
        var_producers: Dict[str, str] = {}

        # 1. 建立节点
        for c in self.raw_cases:
            cid = c["case_id"]
            node = CaseDAGNode(
                case_id=cid,
                case_name=c["case_name"],
                produced_variables=c["produces"],
                consumed_variables=c["consumes"],
                metadata=c["metadata"],
            )
            nodes[cid] = node
            for var in c["produces"]:
                var_producers[var] = cid

        # 2. 建立显式依赖边 (depends_on)
        for c in self.raw_cases:
            cid = c["case_id"]
            for up_id in c["depends_on"]:
                if up_id in nodes and up_id != cid:
                    nodes[cid].upstream_case_ids.add(up_id)
                    nodes[up_id].downstream_case_ids.add(cid)
                    adj_list[up_id].add(cid)
                    edges.append(
                        CaseDAGEdge(
                            edge_id=f"edge_{uuid.uuid4().hex[:8]}",
                            source_case_id=up_id,
                            target_case_id=cid,
                            dependency_type=DependencyType.EXPLICIT_PREREQUISITE,
                        )
                    )

        # 3. 建立隐式数据流依赖边 (produces -> consumes)
        for c in self.raw_cases:
            cid = c["case_id"]
            for var in c["consumes"]:
                if var in var_producers:
                    producer_id = var_producers[var]
                    if producer_id != cid and producer_id not in nodes[cid].upstream_case_ids:
                        nodes[cid].upstream_case_ids.add(producer_id)
                        nodes[producer_id].downstream_case_ids.add(cid)
                        adj_list[producer_id].add(cid)
                        edges.append(
                            CaseDAGEdge(
                                edge_id=f"edge_{uuid.uuid4().hex[:8]}",
                                source_case_id=producer_id,
                                target_case_id=cid,
                                dependency_type=DependencyType.DATA_VARIABLE_FLOW,
                                shared_variables=[var],
                            )
                        )

        # 4. Tarjan 算法检测死锁环路
        cycles = detect_cycles_tarjan(adj_list)
        is_valid = len(cycles) == 0

        # 5. 提取根节点与叶子节点
        roots = [cid for cid, n in nodes.items() if len(n.upstream_case_ids) == 0]
        leaves = [cid for cid, n in nodes.items() if len(n.downstream_case_ids) == 0]

        return CaseDAGGraphResult(
            dag_id=dag_id,
            is_valid_dag=is_valid,
            nodes_count=len(nodes),
            edges_count=len(edges),
            cycles=cycles,
            nodes=nodes,
            edges=edges,
            root_case_ids=sorted(roots),
            leaf_case_ids=sorted(leaves),
        )
