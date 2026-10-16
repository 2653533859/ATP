"""多源基础设施 (DB池/Redis/MQ) 容量水位实时度量器 (T3.1)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ResourceType(str, Enum):
    """基础设施资源类别。"""

    DATABASE_POOL = "DATABASE_POOL"  # 数据库连接池 (如 HikariCP / pgpool)
    REDIS_CACHE = "REDIS_CACHE"  # 缓存内存容量与命中率
    MESSAGE_QUEUE = "MESSAGE_QUEUE"  # 消息队列积压深度 (Kafka / RabbitMQ)
    HOST_SYSTEM = "HOST_SYSTEM"  # 物理/容器节点 CPU 与内存


class WatermarkLevel(str, Enum):
    """容量水位预警等级。"""

    SAFE = "SAFE"  # 水位 < 70%
    WARNING = "WARNING"  # 70% <= 水位 < 85%
    SATURATED = "SATURATED"  # 85% <= 水位 < 95% (逼近极限，需启动限流)
    EXHAUSTED = "EXHAUSTED"  # 水位 >= 95% (饱和耗尽，立即熔断)


@dataclass
class WatermarkItem:
    """单个基础设施资源水位快照。"""

    resource_id: str
    resource_type: ResourceType
    current_value: float
    capacity_limit: float
    utilization_rate_pct: float
    watermark_level: WatermarkLevel
    unit: str
    detail_metric_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "current_value": round(self.current_value, 1),
            "capacity_limit": round(self.capacity_limit, 1),
            "utilization_rate_pct": round(self.utilization_rate_pct, 1),
            "watermark_level": self.watermark_level.value,
            "unit": self.unit,
            "detail_metric_name": self.detail_metric_name,
        }


@dataclass
class CapacityWatermarkAuditReport:
    """多源基础设施容量水位综合评估报告。"""

    report_id: str
    target_cluster_or_env: str
    total_resources_measured: int
    health_load_index_pct: float  # 系统总体健康负荷指数 (0~100%)
    max_utilization_pct: float  # 最高木桶短板利用率
    weakest_bottleneck_resource: str  # 瓶颈木桶短板资源 ID
    requires_avalanche_breaker: bool  # 是否超过 85% 警戒线需触发防雪崩熔断
    watermarks: list[WatermarkItem]
    remediation_actions: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_cluster_or_env": self.target_cluster_or_env,
            "total_resources_measured": self.total_resources_measured,
            "health_load_index_pct": round(self.health_load_index_pct, 1),
            "max_utilization_pct": round(self.max_utilization_pct, 1),
            "weakest_bottleneck_resource": self.weakest_bottleneck_resource,
            "requires_avalanche_breaker": self.requires_avalanche_breaker,
            "watermarks": [w.to_dict() for w in self.watermarks],
            "remediation_actions": self.remediation_actions,
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_WATERMARK_REPORTS: dict[str, CapacityWatermarkAuditReport] = {}


def clear_watermark_report_store() -> None:
    """清空容量水位报告仓库 (单测专用)。"""
    _WATERMARK_REPORTS.clear()


def _evaluate_watermark_level(rate_pct: float) -> WatermarkLevel:
    """按利用率阶梯评定水位预警等级。"""
    if rate_pct < 70.0:
        return WatermarkLevel.SAFE
    if rate_pct < 85.0:
        return WatermarkLevel.WARNING
    if rate_pct < 95.0:
        return WatermarkLevel.SATURATED
    return WatermarkLevel.EXHAUSTED


def meter_infrastructure_capacity_watermark(
    target_cluster_or_env: str,
    metric_samples: list[dict[str, Any]],
) -> CapacityWatermarkAuditReport:
    """采集并聚合多源基础设施监控指标，计算容量水位与健康负荷指数。"""
    watermarks: list[WatermarkItem] = []
    remediation_actions: list[str] = []

    if not metric_samples:
        metric_samples = [
            {
                "resource_id": "db_pool_01",
                "resource_type": "DATABASE_POOL",
                "current_value": 45.0,
                "capacity_limit": 100.0,
                "unit": "connections",
            }
        ]

    for s in metric_samples:
        rid = str(s.get("resource_id") or f"res_{uuid.uuid4().hex[:4]}")
        rtype_str = str(s.get("resource_type") or "DATABASE_POOL").upper()
        try:
            rtype = ResourceType[rtype_str]
        except KeyError:
            rtype = ResourceType.DATABASE_POOL

        cur_val = float(s.get("current_value", 0.0))
        cap_limit = float(s.get("capacity_limit", 100.0))
        unit = str(s.get("unit") or "units")
        metric_name = str(s.get("detail_metric_name") or f"{rtype.value}_utilization")

        # 计算利用率
        if cap_limit > 0:
            util_rate = min(100.0, max(0.0, (cur_val / cap_limit) * 100.0))
        else:
            util_rate = 0.0

        level = _evaluate_watermark_level(util_rate)

        if level in (WatermarkLevel.SATURATED, WatermarkLevel.EXHAUSTED):
            remediation_actions.append(
                f"高危资源 [{rid}] ({rtype.value}) 水位高达 {util_rate:.1f}% ({cur_val:.0f}/{cap_limit:.0f} {unit})，"
                f"建议紧急扩容连接池/规格，并启动压测阶梯降速。"
            )

        watermarks.append(
            WatermarkItem(
                resource_id=rid,
                resource_type=rtype,
                current_value=cur_val,
                capacity_limit=cap_limit,
                utilization_rate_pct=util_rate,
                watermark_level=level,
                unit=unit,
                detail_metric_name=metric_name,
            )
        )

    # 寻找最高利用率短板
    max_item = max(watermarks, key=lambda w: w.utilization_rate_pct)
    max_util = max_item.utilization_rate_pct
    weakest_res = max_item.resource_id

    # 健康指数计算：100 - max_util，最低 0 分
    health_index = max(0.0, min(100.0, 100.0 - max_util))
    requires_breaker = max_util >= 85.0

    if not requires_breaker:
        remediation_actions.append("全链路多源基础设施容量水位平稳，全部处于安全负荷区间内。")

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", target_cluster_or_env)[:16]
    report_id = f"cwm_rpt_{safe_name}_{int(now.timestamp())}"

    report = CapacityWatermarkAuditReport(
        report_id=report_id,
        target_cluster_or_env=target_cluster_or_env,
        total_resources_measured=len(watermarks),
        health_load_index_pct=health_index,
        max_utilization_pct=max_util,
        weakest_bottleneck_resource=weakest_res,
        requires_avalanche_breaker=requires_breaker,
        watermarks=watermarks,
        remediation_actions=remediation_actions,
        created_at=now,
    )

    _WATERMARK_REPORTS[report_id] = report
    return report


def get_watermark_report(report_id: str) -> CapacityWatermarkAuditReport | None:
    """按 ID 查询容量水位报告。"""
    return _WATERMARK_REPORTS.get(report_id)


def list_watermark_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史容量水位报告列表。"""
    reports = list(reversed(list(_WATERMARK_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
