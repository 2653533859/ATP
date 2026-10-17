"""双端 UI 与状态树对齐分析器服务 (T2.1)

对比多端（iOS vs Android / Web vs Mobile）相同业务页面的 UI 控件层级树与状态结构:
1. 跨端 UI 控件状态树统一建模 (ParityScreenTree & ParityNode);
2. 树递归与多特征加权节点对齐算法 (Tree Alignment & Node Matching Matrix);
3. 孤立节点识别 (Source-Only / Target-Only 单端独有控件);
4. 页面级双端对齐率计算与矩阵结构化导出。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.cross_platform_element_translator import (
    SemanticElementDescriptor,
    translate_element,
)


class AlignmentMatchType(str, enum.Enum):
    EXACT = "EXACT"  # 完全匹配 (文案与角色一致)
    SYNONYM = "SYNONYM"  # 同义词匹配 (如 立即支付 vs 确认付款)
    FUZZY = "FUZZY"  # 模糊匹配 (标识符与上下文匹配)
    PARTIAL = "PARTIAL"  # 部分对齐 (文案微小差异)
    UNALIGNED = "UNALIGNED"  # 未对齐


@dataclass
class ParityNode:
    node_id: str
    role: str  # button | input | label | container | image | tab | link
    text: Optional[str] = None
    identifier: Optional[str] = None
    bounding_box: Optional[List[int]] = None
    children: List[ParityNode] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def flatten(self) -> List[ParityNode]:
        """展平获取所有层级下的叶子与子控件列表"""
        nodes: List[ParityNode] = [self]
        for c in self.children:
            nodes.extend(c.flatten())
        return nodes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "text": self.text,
            "identifier": self.identifier,
            "bounding_box": self.bounding_box,
            "children": [c.to_dict() for c in self.children],
            "attributes": self.attributes,
        }


@dataclass
class ParityScreenTree:
    screen_id: str
    screen_name: str
    platform: str  # ios | android | web
    root_node: ParityNode
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "screen_id": self.screen_id,
            "screen_name": self.screen_name,
            "platform": self.platform,
            "root_node": self.root_node.to_dict(),
            "metadata": self.metadata,
        }


@dataclass
class AlignedNodePair:
    pair_id: str
    source_node: ParityNode
    target_node: ParityNode
    alignment_score: float  # 0.0 ~ 1.0
    match_type: AlignmentMatchType
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "source_node": self.source_node.to_dict(),
            "target_node": self.target_node.to_dict(),
            "alignment_score": round(self.alignment_score, 4),
            "match_type": self.match_type.value,
            "notes": self.notes,
        }


@dataclass
class ParityAlignmentMatrix:
    matrix_id: str
    screen_name: str
    source_platform: str
    target_platform: str
    total_source_nodes: int
    total_target_nodes: int
    aligned_pairs_count: int
    source_only_count: int
    target_only_count: int
    overall_alignment_rate: float  # 0.0 ~ 1.0
    aligned_pairs: List[AlignedNodePair]
    source_only_nodes: List[ParityNode]
    target_only_nodes: List[ParityNode]
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matrix_id": self.matrix_id,
            "screen_name": self.screen_name,
            "source_platform": self.source_platform,
            "target_platform": self.target_platform,
            "total_source_nodes": self.total_source_nodes,
            "total_target_nodes": self.total_target_nodes,
            "aligned_pairs_count": self.aligned_pairs_count,
            "source_only_count": self.source_only_count,
            "target_only_count": self.target_only_count,
            "overall_alignment_rate": round(self.overall_alignment_rate, 4),
            "aligned_pairs": [p.to_dict() for p in self.aligned_pairs],
            "source_only_nodes": [n.to_dict() for n in self.source_only_nodes],
            "target_only_nodes": [n.to_dict() for n in self.target_only_nodes],
            "analyzed_at": self.analyzed_at,
        }


def _convert_node_to_descriptor(node: ParityNode, platform: str) -> SemanticElementDescriptor:
    return SemanticElementDescriptor(
        element_id=node.node_id,
        element_type=node.role,
        platform=platform,
        text=node.text,
        identifier=node.identifier,
        bounding_box=node.bounding_box,
    )


def align_screen_trees(
    source_tree: ParityScreenTree,
    target_tree: ParityScreenTree,
    confidence_threshold: float = 0.65,
) -> ParityAlignmentMatrix:
    """对比双端界面控件树，计算节点匹配矩阵与孤立节点"""
    matrix_id = f"matrix_{uuid.uuid4().hex[:12]}"

    src_nodes = [n for n in source_tree.root_node.flatten() if n.role != "container"]
    tgt_nodes = [n for n in target_tree.root_node.flatten() if n.role != "container"]

    src_descriptors = [_convert_node_to_descriptor(n, source_tree.platform) for n in src_nodes]
    tgt_descriptors = [_convert_node_to_descriptor(n, target_tree.platform) for n in tgt_nodes]

    tgt_node_map = {n.node_id: n for n in tgt_nodes}
    matched_target_ids: Set[str] = set()
    aligned_pairs: List[AlignedNodePair] = []
    source_only_nodes: List[ParityNode] = []

    for src_node, src_desc in zip(src_nodes, src_descriptors):
        # 排除已被占用的目标节点
        available_cands = [d for d in tgt_descriptors if d.element_id not in matched_target_ids]
        if not available_cands:
            source_only_nodes.append(src_node)
            continue

        match_res = translate_element(src_desc, available_cands, confidence_threshold)
        if match_res.is_confident and match_res.matched_element:
            target_id = match_res.matched_element.element_id
            matched_target_ids.add(target_id)
            tgt_node = tgt_node_map[target_id]

            # 确定匹配类型
            if match_res.match_strategy == "EXACT_TEXT":
                m_type = AlignmentMatchType.EXACT
            elif match_res.match_strategy == "SYNONYM_TEXT":
                m_type = AlignmentMatchType.SYNONYM
            elif match_res.total_score >= 0.80:
                m_type = AlignmentMatchType.FUZZY
            else:
                m_type = AlignmentMatchType.PARTIAL

            pair = AlignedNodePair(
                pair_id=f"pair_{uuid.uuid4().hex[:8]}",
                source_node=src_node,
                target_node=tgt_node,
                alignment_score=match_res.total_score,
                match_type=m_type,
                notes=f"匹配策略: {match_res.match_strategy}",
            )
            aligned_pairs.append(pair)
        else:
            source_only_nodes.append(src_node)

    # 提取目标端未被任何源端节点匹配的孤立节点
    target_only_nodes = [n for n in tgt_nodes if n.node_id not in matched_target_ids]

    # 计算双端总体对齐率
    denom = max(len(src_nodes), len(tgt_nodes))
    alignment_rate = len(aligned_pairs) / denom if denom > 0 else 1.0

    return ParityAlignmentMatrix(
        matrix_id=matrix_id,
        screen_name=source_tree.screen_name,
        source_platform=source_tree.platform,
        target_platform=target_tree.platform,
        total_source_nodes=len(src_nodes),
        total_target_nodes=len(tgt_nodes),
        aligned_pairs_count=len(aligned_pairs),
        source_only_count=len(source_only_nodes),
        target_only_count=len(target_only_nodes),
        overall_alignment_rate=alignment_rate,
        aligned_pairs=aligned_pairs,
        source_only_nodes=source_only_nodes,
        target_only_nodes=target_only_nodes,
    )
