"""Global Test Asset Full-Scope Dependency Graph & Reverse Indexer Service (C2.1).

Provides:
1. Multi-tier asset dependency graph modeling (Plan -> Suite -> Case -> Dataset/Env/API Endpoint).
2. Bidirectional traversal: forward dependency resolution and reverse consumer impact attribution.
3. Unreferenced orphan asset detection (unused cases, orphan datasets).
4. Sub-graph query for project-scoped asset topology visualization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

VAR_PLACEHOLDER_REGEX = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


class AssetType(str, enum.Enum):
    PLAN = "plan"
    SUITE = "suite"
    CASE = "case"
    DATASET = "dataset"
    ENV = "env"
    API_ENDPOINT = "api_endpoint"
    DEVICE = "device"


class RelationType(str, enum.Enum):
    CONTAINS = "CONTAINS"
    USES_ENV = "USES_ENV"
    DRIVEN_BY_DATASET = "DRIVEN_BY_DATASET"
    CALLS_API = "CALLS_API"
    BINDS_DEVICE = "BINDS_DEVICE"
    REFERENCES_VAR = "REFERENCES_VAR"


@dataclass
class AssetNode:
    node_id: str  # e.g. "case:101", "suite:20", "plan:5", "api_endpoint:POST /orders"
    asset_type: AssetType
    asset_id: str | int
    name: str
    project_id: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "asset_type": self.asset_type.value,
            "asset_id": self.asset_id,
            "name": self.name,
            "project_id": self.project_id,
            "metadata": self.metadata,
        }


@dataclass
class AssetEdge:
    source_node_id: str  # upstream consumer
    target_node_id: str  # downstream dependency
    relation_type: RelationType
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation_type": self.relation_type.value,
            "description": self.description,
        }


class AssetGraphIndexer:
    def __init__(self) -> None:
        self.nodes: dict[str, AssetNode] = {}
        self.forward_edges: dict[str, list[AssetEdge]] = {}  # source -> outgoing
        self.reverse_edges: dict[str, list[AssetEdge]] = {}  # target -> incoming

    def clear(self) -> None:
        self.nodes.clear()
        self.forward_edges.clear()
        self.reverse_edges.clear()

    def add_node(
        self,
        asset_type: AssetType,
        asset_id: str | int,
        name: str,
        project_id: int,
        metadata: dict[str, Any] | None = None,
    ) -> AssetNode:
        node_id = f"{asset_type.value}:{asset_id}"
        node = AssetNode(
            node_id=node_id,
            asset_type=asset_type,
            asset_id=asset_id,
            name=name,
            project_id=project_id,
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        if node_id not in self.forward_edges:
            self.forward_edges[node_id] = []
        if node_id not in self.reverse_edges:
            self.reverse_edges[node_id] = []
        return node

    def add_edge(
        self,
        source_type: AssetType,
        source_id: str | int,
        target_type: AssetType,
        target_id: str | int,
        relation_type: RelationType,
        description: str = "",
    ) -> None:
        src = f"{source_type.value}:{source_id}"
        tgt = f"{target_type.value}:{target_id}"

        edge = AssetEdge(
            source_node_id=src,
            target_node_id=tgt,
            relation_type=relation_type,
            description=description,
        )

        if src not in self.forward_edges:
            self.forward_edges[src] = []
        self.forward_edges[src].append(edge)

        if tgt not in self.reverse_edges:
            self.reverse_edges[tgt] = []
        self.reverse_edges[tgt].append(edge)

    def get_upstream_consumers(
        self,
        asset_type: AssetType,
        asset_id: str | int,
        *,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Query reverse index: who consumes/depends on this asset? (e.g. Case -> Suites -> Plans)."""
        root_id = f"{asset_type.value}:{asset_id}"
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(root_id, 0)]
        consumers: list[dict[str, Any]] = []

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            in_edges = self.reverse_edges.get(curr_id, [])
            for edge in in_edges:
                upstream_id = edge.source_node_id
                if upstream_id not in visited:
                    visited.add(upstream_id)
                    node = self.nodes.get(upstream_id)
                    consumers.append(
                        {
                            "node": node.to_dict() if node else {"node_id": upstream_id},
                            "relation": edge.relation_type.value,
                            "depth": depth + 1,
                        }
                    )
                    queue.append((upstream_id, depth + 1))

        return consumers

    def get_downstream_dependencies(
        self,
        asset_type: AssetType,
        asset_id: str | int,
        *,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Query forward index: what does this asset depend on? (e.g. Plan -> Suites -> Cases -> API Endpoints)."""
        root_id = f"{asset_type.value}:{asset_id}"
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(root_id, 0)]
        dependencies: list[dict[str, Any]] = []

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            out_edges = self.forward_edges.get(curr_id, [])
            for edge in out_edges:
                downstream_id = edge.target_node_id
                if downstream_id not in visited:
                    visited.add(downstream_id)
                    node = self.nodes.get(downstream_id)
                    dependencies.append(
                        {
                            "node": node.to_dict() if node else {"node_id": downstream_id},
                            "relation": edge.relation_type.value,
                            "depth": depth + 1,
                        }
                    )
                    queue.append((downstream_id, depth + 1))

        return dependencies

    def find_orphan_assets(self, project_id: int | None = None) -> dict[str, Any]:
        """Detect unreferenced orphan assets (e.g. cases not in any suite/plan, unused datasets)."""
        orphan_cases: list[dict[str, Any]] = []
        orphan_datasets: list[dict[str, Any]] = []

        for node_id, node in self.nodes.items():
            if project_id is not None and node.project_id != project_id:
                continue

            in_edges = self.reverse_edges.get(node_id, [])
            if not in_edges:
                if node.asset_type == AssetType.CASE:
                    orphan_cases.append(node.to_dict())
                elif node.asset_type == AssetType.DATASET:
                    orphan_datasets.append(node.to_dict())

        return {
            "orphan_cases": orphan_cases,
            "orphan_datasets": orphan_datasets,
            "total_orphans_count": len(orphan_cases) + len(orphan_datasets),
        }

    def export_project_subgraph(self, project_id: int) -> dict[str, Any]:
        """Export project-filtered nodes, directed edges, and asset distribution statistics."""
        proj_nodes = [n for n in self.nodes.values() if n.project_id == project_id]
        node_id_set = {n.node_id for n in proj_nodes}

        proj_edges: list[dict[str, Any]] = []
        for src, edges in self.forward_edges.items():
            if src in node_id_set:
                for e in edges:
                    if e.target_node_id in node_id_set:
                        proj_edges.append(e.to_dict())

        stats = {
            "plans": sum(1 for n in proj_nodes if n.asset_type == AssetType.PLAN),
            "suites": sum(1 for n in proj_nodes if n.asset_type == AssetType.SUITE),
            "cases": sum(1 for n in proj_nodes if n.asset_type == AssetType.CASE),
            "datasets": sum(1 for n in proj_nodes if n.asset_type == AssetType.DATASET),
            "api_endpoints": sum(1 for n in proj_nodes if n.asset_type == AssetType.API_ENDPOINT),
        }

        orphans = self.find_orphan_assets(project_id)

        return {
            "project_id": project_id,
            "total_nodes": len(proj_nodes),
            "total_edges": len(proj_edges),
            "asset_distribution": stats,
            "orphans": orphans,
            "nodes": [n.to_dict() for n in proj_nodes],
            "edges": proj_edges,
        }


# Global in-memory singleton
_GLOBAL_ASSET_INDEXER = AssetGraphIndexer()


def get_global_asset_indexer() -> AssetGraphIndexer:
    return _GLOBAL_ASSET_INDEXER
