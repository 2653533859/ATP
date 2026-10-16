"""压测调用链下游热点慢调用与资源争用瓶颈归因器 (T3.2)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BottleneckRootCauseType(str, Enum):
    """瓶颈根因分类枚举。"""

    LOCK_CONTENTION_DEADLOCK = "LOCK_CONTENTION_DEADLOCK"  # 行锁竞争超时或死锁
    SLOW_DATABASE_QUERY = "SLOW_DATABASE_QUERY"  # 慢 SQL 或缺少索引全表扫描
    THREAD_POOL_EXHAUSTION = "THREAD_POOL_EXHAUSTION"  # 线程池队列打满积压
    DOWNSTREAM_GATEWAY_LATENCY = "DOWNSTREAM_GATEWAY_LATENCY"  # 外部第三方接口调用耗时剧增
    CPU_SATURATION = "CPU_SATURATION"  # 节点 CPU 持续打满算力瓶颈


class BottleneckSeverity(str, Enum):
    """瓶颈严重度。"""

    CRITICAL = "CRITICAL"  # 死锁、线程池瘫痪
    HIGH = "HIGH"  # 慢 SQL、下游恶化
    MEDIUM = "MEDIUM"  # 轻度排队
    LOW = "LOW"  # 次要抖动


@dataclass
class BottleneckFindingItem:
    """单个瓶颈根因发现明细。"""

    finding_id: str
    cause_type: BottleneckRootCauseType
    severity: BottleneckSeverity
    culprit_service: str
    culprit_endpoint_or_sql: str
    measured_duration_ms: float
    impact_description: str
    optimization_recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "cause_type": self.cause_type.value,
            "severity": self.severity.value,
            "culprit_service": self.culprit_service,
            "culprit_endpoint_or_sql": self.culprit_endpoint_or_sql,
            "measured_duration_ms": round(self.measured_duration_ms, 1),
            "impact_description": self.impact_description,
            "optimization_recommendation": self.optimization_recommendation,
        }


@dataclass
class BottleneckClassificationReport:
    """压测瓶颈智能归因全景报告。"""

    report_id: str
    scenario_name: str
    total_spans_analyzed: int
    p50_latency_ms: float
    p90_latency_ms: float
    p99_latency_ms: float
    total_bottlenecks_count: int
    primary_root_cause: str  # 首要主导瓶颈类型
    system_stress_health_score: float  # 0~100 综合得分
    findings: list[BottleneckFindingItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scenario_name": self.scenario_name,
            "total_spans_analyzed": self.total_spans_analyzed,
            "p50_latency_ms": round(self.p50_latency_ms, 1),
            "p90_latency_ms": round(self.p90_latency_ms, 1),
            "p99_latency_ms": round(self.p99_latency_ms, 1),
            "total_bottlenecks_count": self.total_bottlenecks_count,
            "primary_root_cause": self.primary_root_cause,
            "system_stress_health_score": round(self.system_stress_health_score, 1),
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_BOTTLENECK_REPORTS: dict[str, BottleneckClassificationReport] = {}


def clear_bottleneck_report_store() -> None:
    """清空瓶颈归因报告仓库 (单测专用)。"""
    _BOTTLENECK_REPORTS.clear()


def classify_distributed_bottlenecks(
    scenario_name: str,
    spans: list[dict[str, Any]],
) -> BottleneckClassificationReport:
    """深度分析调用链 Span 样本集，量化 P99 延迟，自动归因慢调用、锁争用与线程池瓶颈。"""
    findings: list[BottleneckFindingItem] = []

    if not spans:
        spans = [{"service_name": "gateway", "duration_ms": 20.0}]

    durations = sorted([float(s.get("duration_ms", 0.0)) for s in spans])
    total_count = len(durations)

    # 计算分位数
    p50 = durations[int(total_count * 0.50)]
    p90 = durations[min(total_count - 1, int(total_count * 0.90))]
    p99 = durations[min(total_count - 1, int(total_count * 0.99))]

    cause_counter: dict[BottleneckRootCauseType, int] = {}

    for s in spans:
        s_name = str(s.get("service_name") or "unknown_service").strip()
        endpoint = str(s.get("endpoint_or_sql") or s_name).strip()
        dur = float(s.get("duration_ms", 0.0))
        err_msg = str(s.get("error_message") or "").lower()
        lock_wait = float(s.get("lock_wait_time_ms", 0.0))
        queue_depth = int(s.get("thread_queue_depth", 0))
        cpu_pct = float(s.get("cpu_usage_pct", 0.0))

        # 1. 锁争用与死锁判定 (CRITICAL)
        if lock_wait > 200.0 or any(k in err_msg for k in ("deadlock", "lock wait timeout", "lock_contention")):
            findings.append(
                BottleneckFindingItem(
                    finding_id=f"bt_{uuid.uuid4().hex[:6]}",
                    cause_type=BottleneckRootCauseType.LOCK_CONTENTION_DEADLOCK,
                    severity=BottleneckSeverity.CRITICAL,
                    culprit_service=s_name,
                    culprit_endpoint_or_sql=endpoint,
                    measured_duration_ms=dur,
                    impact_description=f"检测到高危行锁争用或死锁超时 (锁等待耗时: {lock_wait:.1f}ms)，阻塞其他并发事务提交。",
                    optimization_recommendation="缩短长事务耗时、优化索引命中、将加锁操作推迟到事务提交最后阶段，或拆解批量更新。",
                )
            )
            cause_counter[BottleneckRootCauseType.LOCK_CONTENTION_DEADLOCK] = (
                cause_counter.get(BottleneckRootCauseType.LOCK_CONTENTION_DEADLOCK, 0) + 1
            )

        # 2. 线程池打满积压判定 (HIGH)
        elif queue_depth > 50 and dur > 250.0:
            findings.append(
                BottleneckFindingItem(
                    finding_id=f"bt_{uuid.uuid4().hex[:6]}",
                    cause_type=BottleneckRootCauseType.THREAD_POOL_EXHAUSTION,
                    severity=BottleneckSeverity.HIGH,
                    culprit_service=s_name,
                    culprit_endpoint_or_sql=endpoint,
                    measured_duration_ms=dur,
                    impact_description=f"工作线程池队列深度积压达 {queue_depth}，请求进入阻塞排队，导致端到端延迟飙升。",
                    optimization_recommendation="扩容核心线程池配置 (corePoolSize/maxPoolSize)，或拆分异步事件总线异步解耦。",
                )
            )
            cause_counter[BottleneckRootCauseType.THREAD_POOL_EXHAUSTION] = (
                cause_counter.get(BottleneckRootCauseType.THREAD_POOL_EXHAUSTION, 0) + 1
            )

        # 3. 慢数据库查询判定 (HIGH)
        elif dur > 400.0 and any(k in endpoint.upper() for k in ("SELECT", "UPDATE", "INSERT", "DELETE", "FROM")):
            findings.append(
                BottleneckFindingItem(
                    finding_id=f"bt_{uuid.uuid4().hex[:6]}",
                    cause_type=BottleneckRootCauseType.SLOW_DATABASE_QUERY,
                    severity=BottleneckSeverity.HIGH,
                    culprit_service=s_name,
                    culprit_endpoint_or_sql=endpoint,
                    measured_duration_ms=dur,
                    impact_description=f"慢 SQL 执行耗时高达 {dur:.1f}ms，可能存在缺失联合索引或大表全表扫描。",
                    optimization_recommendation="通过 EXPLAIN 执行计划排查索引命中，为高频过滤字段添加复合索引，避免大分页或深 OFFSET。",
                )
            )
            cause_counter[BottleneckRootCauseType.SLOW_DATABASE_QUERY] = (
                cause_counter.get(BottleneckRootCauseType.SLOW_DATABASE_QUERY, 0) + 1
            )

        # 4. 节点 CPU 算力打满 (HIGH)
        elif cpu_pct >= 90.0:
            findings.append(
                BottleneckFindingItem(
                    finding_id=f"bt_{uuid.uuid4().hex[:6]}",
                    cause_type=BottleneckRootCauseType.CPU_SATURATION,
                    severity=BottleneckSeverity.HIGH,
                    culprit_service=s_name,
                    culprit_endpoint_or_sql=endpoint,
                    measured_duration_ms=dur,
                    impact_description=f"服务节点 CPU 水位高达 {cpu_pct:.1f}%，计算密集型任务导致系统上下文频繁切换卡顿。",
                    optimization_recommendation="触发 HPA Pod 弹性水平扩容，或将复杂加密/压缩/批量运算下沉至工作节点处理。",
                )
            )
            cause_counter[BottleneckRootCauseType.CPU_SATURATION] = (
                cause_counter.get(BottleneckRootCauseType.CPU_SATURATION, 0) + 1
            )

        # 5. 下游网关恶化
        elif dur > 800.0:
            findings.append(
                BottleneckFindingItem(
                    finding_id=f"bt_{uuid.uuid4().hex[:6]}",
                    cause_type=BottleneckRootCauseType.DOWNSTREAM_GATEWAY_LATENCY,
                    severity=BottleneckSeverity.MEDIUM,
                    culprit_service=s_name,
                    culprit_endpoint_or_sql=endpoint,
                    measured_duration_ms=dur,
                    impact_description=f"下游依赖接口响应迟缓 ({dur:.1f}ms)，拖慢上游调用链整体响应速度。",
                    optimization_recommendation="配置针对下游调用的超时容错 (Timeout) 与熔断降级策略，避免级联阻塞雪崩。",
                )
            )
            cause_counter[BottleneckRootCauseType.DOWNSTREAM_GATEWAY_LATENCY] = (
                cause_counter.get(BottleneckRootCauseType.DOWNSTREAM_GATEWAY_LATENCY, 0) + 1
            )

    # 首要主导瓶颈类型
    if cause_counter:
        primary_cause = max(cause_counter.items(), key=lambda x: x[1])[0].value
    else:
        primary_cause = "NONE (链路无显著热点瓶颈)"

    # 计算压测健康得分 (100 分制)
    penalty = sum(
        30.0 if f.severity == BottleneckSeverity.CRITICAL else (15.0 if f.severity == BottleneckSeverity.HIGH else 5.0)
        for f in findings
    )
    health_score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", scenario_name)[:16]
    report_id = f"btnk_rpt_{safe_name}_{int(now.timestamp())}"

    report = BottleneckClassificationReport(
        report_id=report_id,
        scenario_name=scenario_name,
        total_spans_analyzed=total_count,
        p50_latency_ms=p50,
        p90_latency_ms=p90,
        p99_latency_ms=p99,
        total_bottlenecks_count=len(findings),
        primary_root_cause=primary_cause,
        system_stress_health_score=health_score,
        findings=findings,
        created_at=now,
    )

    _BOTTLENECK_REPORTS[report_id] = report
    return report


def get_bottleneck_report(report_id: str) -> BottleneckClassificationReport | None:
    """按 ID 查询瓶颈归因报告。"""
    return _BOTTLENECK_REPORTS.get(report_id)


def list_bottleneck_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史瓶颈归因报告列表。"""
    reports = list(reversed(list(_BOTTLENECK_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
