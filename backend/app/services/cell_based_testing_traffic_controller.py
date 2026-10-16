"""多可用区单元化 (Cell/Zone) 流量切流与路由策略控制器 (T2.1)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CellStatus(str, Enum):
    """单元化细胞生命周期状态。"""

    ACTIVE_PROD = "ACTIVE_PROD"  # 正常承载生产流量
    STRESS_ONLY = "STRESS_ONLY"  # 专职压测隔离单元 (禁止承载真实生产订单)
    DRAINING = "DRAINING"  # 正在排空流量 (准备演练或维护)
    ISOLATED_FAILSAFE = "ISOLATED_FAILSAFE"  # 发生异常被紧急物理隔离


@dataclass
class CellDefinition:
    """单个业务单元定义。"""

    cell_id: str
    cell_name: str
    zone: str
    traffic_weight: int  # 权重 0 ~ 100
    status: CellStatus
    allowed_shards: list[int]  # 负责的用户分片 (例如 0~49)
    is_stress_target: bool = False
    active_connections_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "cell_name": self.cell_name,
            "zone": self.zone,
            "traffic_weight": self.traffic_weight,
            "status": self.status.value,
            "allowed_shards": self.allowed_shards,
            "is_stress_target": self.is_stress_target,
            "active_connections_count": self.active_connections_count,
        }


@dataclass
class CellRoutingDecision:
    """单次请求单元化路由决策。"""

    decision_id: str
    user_id: str | None
    is_shadow_traffic: bool
    assigned_cell_id: str
    assigned_zone: str
    is_stress_cell: bool
    shunting_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "user_id": self.user_id,
            "is_shadow_traffic": self.is_shadow_traffic,
            "assigned_cell_id": self.assigned_cell_id,
            "assigned_zone": self.assigned_zone,
            "is_stress_cell": self.is_stress_cell,
            "shunting_reason": self.shunting_reason,
        }


@dataclass
class CellTestingTopologyReport:
    """全景单元化拓扑状态报告。"""

    report_id: str
    total_cells_count: int
    active_prod_cells: int
    stress_cells_count: int
    isolated_cells_count: int
    cells: list[CellDefinition]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_cells_count": self.total_cells_count,
            "active_prod_cells": self.active_prod_cells,
            "stress_cells_count": self.stress_cells_count,
            "isolated_cells_count": self.isolated_cells_count,
            "cells": [c.to_dict() for c in self.cells],
            "created_at": self.created_at.isoformat(),
        }


# 全局默认单元拓扑仓库
_CELL_REGISTRY: dict[str, CellDefinition] = {
    "cell_east_01": CellDefinition(
        "cell_east_01", "华东一区核心生产单元", "cn-east-2a", 50, CellStatus.ACTIVE_PROD, list(range(0, 50)), False
    ),
    "cell_east_02": CellDefinition(
        "cell_east_02", "华东二区核心生产单元", "cn-east-2b", 50, CellStatus.ACTIVE_PROD, list(range(50, 100)), False
    ),
    "cell_stress_sandbox": CellDefinition(
        "cell_stress_sandbox", "压测全链路隔离沙箱单元", "cn-east-2c", 0, CellStatus.STRESS_ONLY, [], True
    ),
}

# 全局拓扑报告历史
_TOPOLOGY_REPORTS: dict[str, CellTestingTopologyReport] = {}


def clear_cell_registry_store() -> None:
    """清空重置单元拓扑仓库 (单测专用)。"""
    _CELL_REGISTRY.clear()
    _TOPOLOGY_REPORTS.clear()
    _CELL_REGISTRY.update(
        {
            "cell_east_01": CellDefinition(
                "cell_east_01",
                "华东一区核心生产单元",
                "cn-east-2a",
                50,
                CellStatus.ACTIVE_PROD,
                list(range(0, 50)),
                False,
            ),
            "cell_east_02": CellDefinition(
                "cell_east_02",
                "华东二区核心生产单元",
                "cn-east-2b",
                50,
                CellStatus.ACTIVE_PROD,
                list(range(50, 100)),
                False,
            ),
            "cell_stress_sandbox": CellDefinition(
                "cell_stress_sandbox", "压测全链路隔离沙箱单元", "cn-east-2c", 0, CellStatus.STRESS_ONLY, [], True
            ),
        }
    )


def register_cell(
    cell_id: str,
    cell_name: str,
    zone: str,
    traffic_weight: int = 50,
    status: CellStatus = CellStatus.ACTIVE_PROD,
    allowed_shards: list[int] | None = None,
    is_stress_target: bool = False,
) -> CellDefinition:
    """注册或更新业务单元。"""
    shards = allowed_shards if allowed_shards is not None else []
    cell = CellDefinition(
        cell_id=cell_id.strip(),
        cell_name=cell_name.strip(),
        zone=zone.strip(),
        traffic_weight=max(0, min(100, traffic_weight)),
        status=status,
        allowed_shards=shards,
        is_stress_target=is_stress_target,
    )
    _CELL_REGISTRY[cell_id.strip()] = cell
    return cell


def list_cells() -> list[dict[str, Any]]:
    """获取所有已注册的业务单元拓扑列表。"""
    return [c.to_dict() for c in _CELL_REGISTRY.values()]


def update_cell_weights(weights_map: dict[str, int]) -> list[dict[str, Any]]:
    """批量调整单元的流量分流权重。"""
    for cid, w in weights_map.items():
        if cid in _CELL_REGISTRY:
            _CELL_REGISTRY[cid].traffic_weight = max(0, min(100, int(w)))
    return list_cells()


def route_request_to_cell(
    user_id: str | None = None,
    is_shadow_traffic: bool = False,
    headers: dict[str, Any] | None = None,
) -> CellRoutingDecision:
    """根据入站上下文 (是否影子流量、用户分片、权重) 智能判定归属单元。"""
    headers = headers or {}
    decision_id = f"dec_{uuid.uuid4().hex[:8]}"

    # 1. 影子压测流量隔离控制：优先重定向至专属压测沙箱单元
    if is_shadow_traffic or headers.get("X-ATP-Shadow") == "true":
        stress_cells = [
            c for c in _CELL_REGISTRY.values() if (c.is_stress_target or c.status == CellStatus.STRESS_ONLY)
        ]
        if stress_cells:
            target = stress_cells[0]
            return CellRoutingDecision(
                decision_id=decision_id,
                user_id=user_id,
                is_shadow_traffic=True,
                assigned_cell_id=target.cell_id,
                assigned_zone=target.zone,
                is_stress_cell=True,
                shunting_reason="识别到影子压测流量，安全重定向至专属压测隔离单元，严防污染核心生产单元。",
            )

    # 2. 正常生产流量：分流至健康的 ACTIVE_PROD 单元
    active_cells = [c for c in _CELL_REGISTRY.values() if c.status == CellStatus.ACTIVE_PROD]
    if not active_cells:
        # 降级容灾：若无活跃生产单元，寻找备用
        fallback = list(_CELL_REGISTRY.values())[0]
        return CellRoutingDecision(
            decision_id=decision_id,
            user_id=user_id,
            is_shadow_traffic=is_shadow_traffic,
            assigned_cell_id=fallback.cell_id,
            assigned_zone=fallback.zone,
            is_stress_cell=fallback.is_stress_target,
            shunting_reason="无健康 ACTIVE_PROD 单元，触发紧急容灾兜底路由。",
        )

    # 基于 user_id 取模进行分片路由
    if user_id:
        # 取模 100
        digits = re.findall(r"\d+", user_id)
        shard_key = int(digits[-1]) % 100 if digits else (hash(user_id) % 100)
        for c in active_cells:
            if shard_key in c.allowed_shards:
                return CellRoutingDecision(
                    decision_id=decision_id,
                    user_id=user_id,
                    is_shadow_traffic=False,
                    assigned_cell_id=c.cell_id,
                    assigned_zone=c.zone,
                    is_stress_cell=False,
                    shunting_reason=f"用户分片 #{shard_key} 精确命中单元分片策略 [{c.cell_name}]。",
                )

    # 默认按最高权重或首个可用单元分流
    chosen = max(active_cells, key=lambda x: x.traffic_weight)
    return CellRoutingDecision(
        decision_id=decision_id,
        user_id=user_id,
        is_shadow_traffic=False,
        assigned_cell_id=chosen.cell_id,
        assigned_zone=chosen.zone,
        is_stress_cell=False,
        shunting_reason=f"无分片键或按权重优选分流至单元 [{chosen.cell_name}] (权重: {chosen.traffic_weight})。",
    )


def generate_cell_topology_report() -> CellTestingTopologyReport:
    """生成当前单元化拓扑全景状态报告。"""
    cells = list(_CELL_REGISTRY.values())
    active_prod = sum(1 for c in cells if c.status == CellStatus.ACTIVE_PROD)
    stress_c = sum(1 for c in cells if (c.is_stress_target or c.status == CellStatus.STRESS_ONLY))
    isolated_c = sum(1 for c in cells if c.status in (CellStatus.ISOLATED_FAILSAFE, CellStatus.DRAINING))

    now = datetime.now(timezone.utc)
    report_id = f"topo_rpt_{int(now.timestamp())}_{uuid.uuid4().hex[:4]}"
    report = CellTestingTopologyReport(
        report_id=report_id,
        total_cells_count=len(cells),
        active_prod_cells=active_prod,
        stress_cells_count=stress_c,
        isolated_cells_count=isolated_c,
        cells=cells,
        created_at=now,
    )
    _TOPOLOGY_REPORTS[report_id] = report
    return report
