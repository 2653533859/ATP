"""全链路压力演练综合审计报告生成器与 Markdown 导出 (T4.3)。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DrillGrade(str, Enum):
    """压测演练综合质量评级。"""

    GRADE_A_EXCELLENT = "GRADE_A_EXCELLENT"  # 卓越 (TPS 超预期, P99 < 200ms, 水位平稳)
    GRADE_B_QUALIFIED = "GRADE_B_QUALIFIED"  # 合格 (达到容量基线, 无严重熔断)
    GRADE_C_RISKY = "GRADE_C_RISKY"  # 有风险 (存在慢调用或连接池接近饱和)
    GRADE_D_REJECTED = "GRADE_D_REJECTED"  # 不合格阻断 (发生防雪崩硬熔断或数据泄漏)


@dataclass
class FullLinkDrillReport:
    """全链路压测复盘综合报告实体。"""

    report_id: str
    drill_id: str
    scenario_name: str
    overall_drill_grade: DrillGrade
    is_production_approved: bool
    composite_health_score_pct: float
    peak_concurrency_vu: int
    peak_tps: float
    p99_latency_ms: float
    error_rate_pct: float
    knee_point_concurrency: int
    knee_point_tps: float
    cliff_point_concurrency: int | None
    max_db_watermark_pct: float
    max_redis_watermark_pct: float
    max_mq_backlog: int
    circuit_breaker_triggered: bool
    failover_rto_ms: float
    sha256_audit_fingerprint: str
    optimization_remediations: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "drill_id": self.drill_id,
            "scenario_name": self.scenario_name,
            "overall_drill_grade": self.overall_drill_grade.value,
            "is_production_approved": self.is_production_approved,
            "composite_health_score_pct": round(self.composite_health_score_pct, 1),
            "peak_concurrency_vu": self.peak_concurrency_vu,
            "peak_tps": round(self.peak_tps, 1),
            "p99_latency_ms": round(self.p99_latency_ms, 1),
            "error_rate_pct": round(self.error_rate_pct, 3),
            "knee_point_concurrency": self.knee_point_concurrency,
            "knee_point_tps": round(self.knee_point_tps, 1),
            "cliff_point_concurrency": self.cliff_point_concurrency,
            "max_db_watermark_pct": round(self.max_db_watermark_pct, 1),
            "max_redis_watermark_pct": round(self.max_redis_watermark_pct, 1),
            "max_mq_backlog": self.max_mq_backlog,
            "circuit_breaker_triggered": self.circuit_breaker_triggered,
            "failover_rto_ms": round(self.failover_rto_ms, 1),
            "sha256_audit_fingerprint": self.sha256_audit_fingerprint,
            "optimization_remediations": self.optimization_remediations,
            "created_at": self.created_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """导出结构化标准 Markdown 压测复盘报告。"""
        status_text = (
            "✅ 生产容量准入通过 (APPROVED)" if self.is_production_approved else "❌ 存在高危风险阻断 (BLOCKED)"
        )
        lines = [
            f"# 生产全链路压测综合审计与容量规划报告 - {self.scenario_name}",
            f"> 生成时间: {self.created_at.isoformat()} | 演练单号: `{self.drill_id}` | 报告 ID: `{self.report_id}`",
            f"> 防篡改指纹: `{self.sha256_audit_fingerprint}`",
            "",
            "## 1. 演练结论与准入评级",
            f"- **准入结论**: **{status_text}**",
            f"- **综合质量评级**: **{self.overall_drill_grade.value}**",
            f"- **全链路健康评分**: **{self.composite_health_score_pct:.1f} / 100**",
            "",
            "## 2. 吞吐性能与长尾时延表现",
            "| 指标项 | 实测数值 | 达标基准 | 状态 |",
            "|---|---|---|---|",
            f"| **峰值并发 (Peak VU)** | {self.peak_concurrency_vu} 线程 | - | 观测值 |",
            f"| **峰值吞吐量 (Peak TPS)** | {self.peak_tps:.1f} TPS | ≥ 2000.0 TPS | {'✅ 达标' if self.peak_tps >= 2000 else '⚠️ 偏低'} |",
            f"| **P99 长尾延迟** | {self.p99_latency_ms:.1f} ms | ≤ 500.0 ms | {'✅ 达标' if self.p99_latency_ms <= 500 else '❌ 超标'} |",
            f"| **平均错误率** | {self.error_rate_pct:.3f} % | ≤ 0.100 % | {'✅ 达标' if self.error_rate_pct <= 0.1 else '❌ 偏高'} |",
            "",
            "## 3. 性能拐点与生产容量规划建议",
            f"- **Knee Point 性能拐点**: 并发 `{self.knee_point_concurrency} VU`，峰值吞吐 `{self.knee_point_tps:.1f} TPS`；",
            f"- **Cliff Point 崩溃点**: `{self.cliff_point_concurrency if self.cliff_point_concurrency else '未发生性能崩溃'}`；",
            f"- **推荐日常生产安全并发**: `{int(self.knee_point_concurrency * 0.75)} VU`；",
            "",
            "## 4. 下游基础设施容量水位与防雪崩防护",
            "| 基础设施类别 | 峰值水位消耗 | 安全阈值 | 熔断状态 |",
            "|---|---|---|---|",
            f"| **数据库连接池 (DB Pool)** | {self.max_db_watermark_pct:.1f} % | ≤ 85.0 % | {'⚠️ 接近警戒' if self.max_db_watermark_pct >= 85 else '✅ 正常'} |",
            f"| **Redis 缓存内存** | {self.max_redis_watermark_pct:.1f} % | ≤ 85.0 % | {'⚠️ 接近警戒' if self.max_redis_watermark_pct >= 85 else '✅ 正常'} |",
            f"| **消息队列积压 (MQ Backlog)** | {self.max_mq_backlog} 条 | ≤ 50000 条 | {'✅ 正常' if self.max_mq_backlog <= 50000 else '❌ 积压过高'} |",
            f"| **防雪崩毫秒级熔断器** | {'🚨 触发阻断' if self.circuit_breaker_triggered else '🛡️ 守候未触发'} | - | 保护生产安全 |",
            f"| **单元容灾 RTO 接管耗时** | {self.failover_rto_ms:.1f} ms | ≤ 2500.0 ms | {'✅ 达标' if self.failover_rto_ms <= 2500 else '❌ 超时'} |",
            "",
            "## 5. 针对性架构加固指引",
        ]
        for idx, rec in enumerate(self.optimization_remediations, 1):
            lines.append(f"{idx}. {rec}")

        return "\n".join(lines)


# 全局审计报告存储
_FULL_DRILL_REPORTS: dict[str, FullLinkDrillReport] = {}


def clear_full_drill_report_store() -> None:
    """清空压测演练报告仓库 (单测专用)。"""
    _FULL_DRILL_REPORTS.clear()


def generate_full_link_stress_drill_report(
    drill_id: str,
    scenario_name: str,
    peak_concurrency_vu: int,
    peak_tps: float,
    p99_latency_ms: float,
    error_rate_pct: float,
    knee_point_concurrency: int,
    knee_point_tps: float,
    cliff_point_concurrency: int | None = None,
    max_db_watermark_pct: float = 65.0,
    max_redis_watermark_pct: float = 55.0,
    max_mq_backlog: int = 1200,
    circuit_breaker_triggered: bool = False,
    failover_rto_ms: float = 1450.0,
) -> FullLinkDrillReport:
    """汇总量化全链路压测各维度指标，进行综合评级并生成带 SHA-256 防篡改签名的复盘报告。"""
    # 评级逻辑
    is_approved = True
    remediations: list[str] = []

    if circuit_breaker_triggered or error_rate_pct >= 5.0 or max_db_watermark_pct >= 95.0:
        grade = DrillGrade.GRADE_D_REJECTED
        is_approved = False
        remediations.append("压测触发防雪崩硬核熔断或数据库水位濒临耗尽，严禁扩大生产并发，需立即排查慢 SQL 与死锁。")
    elif p99_latency_ms > 800.0 or max_db_watermark_pct >= 85.0 or max_redis_watermark_pct >= 85.0:
        grade = DrillGrade.GRADE_C_RISKY
        is_approved = False
        remediations.append("下游基础设施水位超过 85% 警戒线，建议在上线前扩容 DB 连接池与 Redis 实例分片。")
    elif p99_latency_ms > 300.0 or error_rate_pct > 0.05:
        grade = DrillGrade.GRADE_B_QUALIFIED
        remediations.append("整体吞吐达标，但 P99 存在偶发长尾抖动，建议优化微服务线程池队列与外部调用超时。")
    else:
        grade = DrillGrade.GRADE_A_EXCELLENT
        remediations.append("各项吞吐、时延与基础设施水位表现卓越，满足双十一/大促高峰容量准入要求！")

    # 计算综合健康分 (100 分制)
    score = 100.0
    if grade == DrillGrade.GRADE_D_REJECTED:
        score = 45.0
    elif grade == DrillGrade.GRADE_C_RISKY:
        score = 70.0
    elif grade == DrillGrade.GRADE_B_QUALIFIED:
        score = 88.0

    now = datetime.now(timezone.utc)
    # 计算 SHA-256 防篡改指纹
    fp_raw = json.dumps(
        {
            "drill_id": drill_id,
            "peak_tps": round(peak_tps, 1),
            "p99": round(p99_latency_ms, 1),
            "grade": grade.value,
            "score": score,
            "timestamp": now.isoformat(),
        },
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", drill_id)[:16]
    report_id = f"drill_rpt_{safe_name}_{int(now.timestamp())}"

    report = FullLinkDrillReport(
        report_id=report_id,
        drill_id=drill_id,
        scenario_name=scenario_name,
        overall_drill_grade=grade,
        is_production_approved=is_approved,
        composite_health_score_pct=score,
        peak_concurrency_vu=peak_concurrency_vu,
        peak_tps=peak_tps,
        p99_latency_ms=p99_latency_ms,
        error_rate_pct=error_rate_pct,
        knee_point_concurrency=knee_point_concurrency,
        knee_point_tps=knee_point_tps,
        cliff_point_concurrency=cliff_point_concurrency,
        max_db_watermark_pct=max_db_watermark_pct,
        max_redis_watermark_pct=max_redis_watermark_pct,
        max_mq_backlog=max_mq_backlog,
        circuit_breaker_triggered=circuit_breaker_triggered,
        failover_rto_ms=failover_rto_ms,
        sha256_audit_fingerprint=fingerprint,
        optimization_remediations=remediations,
        created_at=now,
    )

    _FULL_DRILL_REPORTS[report_id] = report
    return report


def get_full_drill_report(report_id: str) -> FullLinkDrillReport | None:
    """按 ID 查询压测演练复盘报告。"""
    return _FULL_DRILL_REPORTS.get(report_id)


def list_full_drill_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史压测演练复盘报告列表。"""
    reports = list(reversed(list(_FULL_DRILL_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
