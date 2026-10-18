"""影子数据隔离防污染巡检与影子库表清理器服务 (T2.3)

全量保障生产全链路压测数据隔离防污染，并在压测后安全归档与清理影子存储:
1. 影子存储资产动态巡检探测 (scan_shadow_resources: 识别影子表、影子库、影子Redis、影子Topic);
2. 生产主库防误清核心熔断安全门禁 (严禁对任何非影子资源执行清理，非法目标绝对拦截拒绝 REJECTED);
3. 压测影子数据一键安全清理与预演 (execute_shadow_data_clean: 支持 dry_run 试运行预演与批量安全清空);
4. 综合数据隔离巡检与存储清理审计报告输出 (ShadowDataCleanReport)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ShadowTargetType(str, enum.Enum):
    SHADOW_TABLE = "SHADOW_TABLE"  # 数据库影子表 (如 t_order_shadow)
    SHADOW_DATABASE = "SHADOW_DATABASE"  # 独立影子数据库 (如 db_mall_shadow)
    SHADOW_REDIS_NAMESPACE = "SHADOW_REDIS_NAMESPACE"  # Redis 缓存影子命名空间 (如 shadow:*)
    SHADOW_MQ_TOPIC = "SHADOW_MQ_TOPIC"  # 消息队列影子 Topic (如 topic_order_shadow)


# 合法影子特征规则
LEGITIMATE_SHADOW_PATTERNS = [
    r".*_shadow\b",
    r".*_stress\b",
    r".*_sandbox\b",
    r"^shadow:.*",
    r".*shadow_.*",
    r".*stress_.*",
]

# 绝对禁止执行清理的生产核心表名单 (双重防误清保护)
CRITICAL_PRODUCTION_MASTER_TABLES = [
    r"t_order\b",
    r"t_order_item\b",
    r"t_account_balance\b",
    r"t_payment_record\b",
    r"t_inventory_stock\b",
    r"t_billing_settlement\b",
    r"t_users\b",
]


@dataclass
class ShadowResourceScanItem:
    resource_id: str
    resource_name: str
    target_type: ShadowTargetType
    is_legitimate_shadow: bool
    estimated_records_count: int
    estimated_size_mb: float
    target_service: str
    last_activity_time: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ShadowDataCleanReport:
    clean_job_id: str
    target_service: str
    is_dry_run: bool
    cleaned_resources_count: int
    total_purged_records: int
    reclaimed_space_mb: float
    purged_details: List[Dict[str, Any]]
    rejected_attempts: List[str]
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean_job_id": self.clean_job_id,
            "target_service": self.target_service,
            "is_dry_run": self.is_dry_run,
            "cleaned_resources_count": self.cleaned_resources_count,
            "total_purged_records": self.total_purged_records,
            "reclaimed_space_mb": round(self.reclaimed_space_mb, 2),
            "purged_details": self.purged_details,
            "rejected_attempts": self.rejected_attempts,
            "executed_at": self.executed_at,
        }


def is_safe_shadow_resource(resource_name: str) -> bool:
    """严格核验目标资源是否属于合法安全的影子存储 (严防误删真实生产数据)"""
    r_lower = resource_name.lower().strip()

    # 1. 如果命中核心生产主表特征，绝对拒绝！
    for pat in CRITICAL_PRODUCTION_MASTER_TABLES:
        if re.search(pat, r_lower):
            return False

    # 2. 必须符合合法影子命名后缀或前缀
    for pat in LEGITIMATE_SHADOW_PATTERNS:
        if re.search(pat, r_lower):
            return True

    return False


def scan_shadow_resources(
    target_service: str = "order-service",
    custom_resources: Optional[List[Dict[str, Any]]] = None,
) -> List[ShadowResourceScanItem]:
    """巡检发现微服务关联的影子存储资源清单"""
    if custom_resources is not None:
        items: List[ShadowResourceScanItem] = []
        for r in custom_resources:
            name = r.get("resource_name", "unknown")
            items.append(
                ShadowResourceScanItem(
                    resource_id=r.get("resource_id", f"res_{uuid.uuid4().hex[:8]}"),
                    resource_name=name,
                    target_type=ShadowTargetType(r.get("target_type", "SHADOW_TABLE")),
                    is_legitimate_shadow=is_safe_shadow_resource(name),
                    estimated_records_count=r.get("estimated_records_count", 0),
                    estimated_size_mb=r.get("estimated_size_mb", 0.0),
                    target_service=target_service,
                )
            )
        return items

    # 预设种子巡检资源库 (标准微服务影子环境)
    seed_data = [
        ("t_order_shadow", ShadowTargetType.SHADOW_TABLE, 125000, 245.5),
        ("t_order_item_shadow", ShadowTargetType.SHADOW_TABLE, 350000, 480.2),
        ("shadow:cart:cache", ShadowTargetType.SHADOW_REDIS_NAMESPACE, 45000, 18.0),
        ("topic_order_created_shadow", ShadowTargetType.SHADOW_MQ_TOPIC, 125000, 120.0),
    ]

    return [
        ShadowResourceScanItem(
            resource_id=f"res_{uuid.uuid4().hex[:8]}",
            resource_name=name,
            target_type=t_type,
            is_legitimate_shadow=is_safe_shadow_resource(name),
            estimated_records_count=cnt,
            estimated_size_mb=size,
            target_service=target_service,
        )
        for name, t_type, cnt, size in seed_data
    ]


def execute_shadow_data_clean(
    target_resources: List[str],
    is_dry_run: bool = False,
    target_service: str = "order-service",
) -> ShadowDataCleanReport:
    """执行影子数据一键安全清理与预演"""
    job_id = f"cln_job_{uuid.uuid4().hex[:10]}"
    purged: List[Dict[str, Any]] = []
    rejected: List[str] = []
    total_records = 0
    total_space = 0.0

    # 模拟已知影子资源的记录基数
    mock_stat_map = {
        "t_order_shadow": (125000, 245.5),
        "t_order_item_shadow": (350000, 480.2),
        "shadow:cart:cache": (45000, 18.0),
        "topic_order_created_shadow": (125000, 120.0),
        "t_payment_record_shadow": (80000, 150.0),
    }

    for res in target_resources:
        # 安全卡点审查
        if not is_safe_shadow_resource(res):
            rejected.append(f"非法目标 [{res}]：不是合法的影子存储或属于生产真实主表，系统已绝对拦截，严禁清理！")
            continue

        records, space = mock_stat_map.get(res, (10000, 20.0))
        total_records += records
        total_space += space

        purged.append(
            {
                "resource_name": res,
                "status": "DRY_RUN_SIMULATED" if is_dry_run else "PURGED_SUCCESS",
                "purged_records": records,
                "reclaimed_mb": space,
                "action_detail": f"已{'模拟清空' if is_dry_run else '安全截断清空'}影子库表记录",
            }
        )

    return ShadowDataCleanReport(
        clean_job_id=job_id,
        target_service=target_service,
        is_dry_run=is_dry_run,
        cleaned_resources_count=len(purged),
        total_purged_records=total_records,
        reclaimed_space_mb=total_space,
        purged_details=purged,
        rejected_attempts=rejected,
    )
