"""跨协议多跳调用链拓扑血缘重构器服务 (T2.3)

解析企业级复杂微服务调用链包含的多种异构协议:
HTTP / REST、gRPC、Kafka / RocketMQ / RabbitMQ、Database (Postgres/MySQL/Redis),
将扁平无序的 Span 列表重构为:
1. 具备深度与自耗时 (Self-Time) 计算的层级调用树 (Hierarchical Span Tree);
2. 服务间有向依赖血缘图 (Service Dependency DAG: Nodes & Edges);
3. 全链路串行耗时关键路径 (Critical Path);
4. 多协议覆盖率与最大调用跳数统计 (Max Hops & Protocol Matrix)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


@dataclass
class TopologyNode:
    service_name: str
    service_type: str  # gateway, http, rpc, mq, db, cache
    protocol: str
    span_count: int = 0
    total_duration_ms: float = 0.0
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        avg_dur = self.total_duration_ms / max(1, self.span_count)
        return {
            "service_name": self.service_name,
            "service_type": self.service_type,
            "protocol": self.protocol,
            "span_count": self.span_count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "avg_duration_ms": round(avg_dur, 2),
            "error_count": self.error_count,
            "error_rate": round(self.error_count / max(1, self.span_count), 4),
        }


@dataclass
class TopologyEdge:
    source_service: str
    target_service: str
    protocol: str
    call_count: int = 0
    total_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_service": self.source_service,
            "target_service": self.target_service,
            "protocol": self.protocol,
            "call_count": self.call_count,
            "avg_latency_ms": round(self.total_latency_ms / max(1, self.call_count), 2),
        }


@dataclass
class TraceTopologyLineage:
    trace_id: str
    total_spans: int
    services_count: int
    max_depth_hops: int
    protocols_covered: List[str]
    root_service: str
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
    hierarchical_tree: List[Dict[str, Any]]
    critical_path_span_ids: List[str]
    built_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_spans": self.total_spans,
            "services_count": self.services_count,
            "max_depth_hops": self.max_depth_hops,
            "protocols_covered": self.protocols_covered,
            "root_service": self.root_service,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "hierarchical_tree": self.hierarchical_tree,
            "critical_path_span_ids": self.critical_path_span_ids,
            "built_at": self.built_at,
        }


# 全局轻量级拓扑血缘存储
_TOPOLOGY_LINEAGE_STORE: Dict[str, TraceTopologyLineage] = {}


def clear_topology_lineage_store() -> None:
    _TOPOLOGY_LINEAGE_STORE.clear()


def list_topology_lineages(limit: int = 50) -> List[Dict[str, Any]]:
    return [t.to_dict() for t in list(_TOPOLOGY_LINEAGE_STORE.values())[-limit:]]


def get_topology_lineage(trace_id: str) -> Optional[Dict[str, Any]]:
    lineage = _TOPOLOGY_LINEAGE_STORE.get(trace_id)
    return lineage.to_dict() if lineage else None


def _infer_protocol_and_type(span: Dict[str, Any]) -> tuple[str, str]:
    """根据 Span 的属性推断通讯协议和组件类型"""
    attrs = span.get("attributes", {})
    name = str(span.get("name", "")).lower()

    if "db.system" in attrs or "sql" in name or "db" in name:
        db_sys = str(attrs.get("db.system", "sql")).lower()
        if "redis" in db_sys or "memcached" in db_sys:
            return "redis", "cache"
        return db_sys, "db"

    if "messaging.system" in attrs or "kafka" in name or "rocketmq" in name or "rabbitmq" in name:
        mq_sys = str(attrs.get("messaging.system", "mq")).lower()
        return mq_sys, "mq"

    if "rpc.system" in attrs or "grpc" in name or "thrift" in name or "dubbo" in name:
        rpc_sys = str(attrs.get("rpc.system", "grpc")).lower()
        return rpc_sys, "rpc"

    if "gateway" in str(span.get("service_name", "")).lower():
        return "http", "gateway"

    return "http", "http"


def build_cross_protocol_lineage(
    trace_id: str,
    spans: List[Dict[str, Any]],
) -> TraceTopologyLineage:
    """将跨协议 Span 列表重构为树形调用层级与服务依赖血缘图"""
    if not spans:
        return TraceTopologyLineage(
            trace_id=trace_id,
            total_spans=0,
            services_count=0,
            max_depth_hops=0,
            protocols_covered=[],
            root_service="unknown",
            nodes=[],
            edges=[],
            hierarchical_tree=[],
            critical_path_span_ids=[],
        )

    # 1. 构建字典与节点初始化
    span_map: Dict[str, Dict[str, Any]] = {}
    service_nodes: Dict[str, TopologyNode] = {}
    edges_map: Dict[tuple[str, str, str], TopologyEdge] = {}
    protocols: Set[str] = set()

    for s in spans:
        sid = str(s.get("span_id", ""))
        span_map[sid] = dict(s)
        s_name = str(s.get("service_name", "unknown_service"))
        dur = float(s.get("duration_ms", 0.0))

        proto, s_type = _infer_protocol_and_type(s)
        protocols.add(proto)

        if s_name not in service_nodes:
            service_nodes[s_name] = TopologyNode(
                service_name=s_name,
                service_type=s_type,
                protocol=proto,
            )

        node = service_nodes[s_name]
        node.span_count += 1
        node.total_duration_ms += dur

        status_info = s.get("status", {})
        code = str(status_info.get("code", "")).upper()
        if code in ("STATUS_CODE_ERROR", "ERROR", "2") or bool(s.get("error")):
            node.error_count += 1

    # 2. 边关系 (Edges) 与树状结构初始化
    children_map: Dict[str, List[str]] = {sid: [] for sid in span_map}
    root_ids: List[str] = []

    for sid, s in span_map.items():
        pid = str(s.get("parent_span_id") or "")
        if pid and pid in span_map:
            children_map[pid].append(sid)
            parent_svc = str(span_map[pid].get("service_name", "unknown"))
            curr_svc = str(s.get("service_name", "unknown"))
            proto, _ = _infer_protocol_and_type(s)

            if parent_svc != curr_svc:
                edge_key = (parent_svc, curr_svc, proto)
                if edge_key not in edges_map:
                    edges_map[edge_key] = TopologyEdge(
                        source_service=parent_svc,
                        target_service=curr_svc,
                        protocol=proto,
                    )
                edge = edges_map[edge_key]
                edge.call_count += 1
                edge.total_latency_ms += float(s.get("duration_ms", 0.0))
        else:
            root_ids.append(sid)

    # 3. 递归构建树形结构并计算 Depth 与 Self-Time
    max_depth = [0]
    critical_path: List[str] = []

    def _build_tree(node_id: str, current_depth: int) -> Dict[str, Any]:
        if current_depth > max_depth[0]:
            max_depth[0] = current_depth

        curr_span = span_map[node_id]
        dur = float(curr_span.get("duration_ms", 0.0))
        proto, s_type = _infer_protocol_and_type(curr_span)

        child_nodes = []
        children_total_dur = 0.0

        for cid in children_map.get(node_id, []):
            child_tree = _build_tree(cid, current_depth + 1)
            child_nodes.append(child_tree)
            children_total_dur += float(span_map[cid].get("duration_ms", 0.0))

        self_time = max(0.0, dur - children_total_dur)

        return {
            "span_id": node_id,
            "name": curr_span.get("name", "span"),
            "service_name": curr_span.get("service_name", "unknown"),
            "service_type": s_type,
            "protocol": proto,
            "depth": current_depth,
            "start_time_ms": curr_span.get("start_time_ms", 0.0),
            "end_time_ms": curr_span.get("end_time_ms", 0.0),
            "duration_ms": round(dur, 2),
            "self_time_ms": round(self_time, 2),
            "children": child_nodes,
        }

    tree_roots = [_build_tree(rid, 1) for rid in root_ids]

    # 4. 识别耗时关键路径 (Critical Path): 沿每层耗时最长的子节点延伸
    if root_ids:
        cur_id = max(root_ids, key=lambda i: float(span_map[i].get("duration_ms", 0.0)))
        critical_path.append(cur_id)
        while children_map.get(cur_id):
            cur_id = max(children_map[cur_id], key=lambda i: float(span_map[i].get("duration_ms", 0.0)))
            critical_path.append(cur_id)

    root_svc = span_map[root_ids[0]].get("service_name", "unknown") if root_ids else "unknown"

    lineage = TraceTopologyLineage(
        trace_id=trace_id,
        total_spans=len(spans),
        services_count=len(service_nodes),
        max_depth_hops=max_depth[0],
        protocols_covered=sorted(list(protocols)),
        root_service=root_svc,
        nodes=list(service_nodes.values()),
        edges=list(edges_map.values()),
        hierarchical_tree=tree_roots,
        critical_path_span_ids=critical_path,
    )
    _TOPOLOGY_LINEAGE_STORE[trace_id] = lineage
    return lineage
