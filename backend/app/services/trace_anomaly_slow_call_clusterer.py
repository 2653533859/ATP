"""分布式调用链路异常波动与高频慢调用智能聚类诊断引擎 (T1.3)。

基于分布式追踪 Span 耗时分布、错误模式与时延波动度：
1. 自动聚类慢调用簇与异常模式 (TIMEOUT / 5XX / SLOW_DB / CIRCUIT_BREAKER / DEVIATION)；
2. 量化异常偏离度 (Deviation Sigma / Z-Score 偏离标准差倍数) 与 P95 时延；
3. 输出按破坏影响面加权排序的慢调用根因诊断报告与专家调优建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import math
from typing import Any

from app.services.distributed_trace_telemetry_relay import (
    reconstruct_trace_tree,
)
import app.services.distributed_trace_telemetry_relay as telemetry_relay

logger = logging.getLogger(__name__)


class AnomalyPattern(str, Enum):
    TIMEOUT_BREACH = "TIMEOUT_BREACH"  # 超时熔断或响应截断
    DOWNSTREAM_SERVICE_5XX = "DOWNSTREAM_SERVICE_5XX"  # 下游服务 5xx 故障
    SLOW_DATABASE_QUERY = "SLOW_DATABASE_QUERY"  # 数据库慢查询/未命中索引
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"  # 断路器跳闸或降级熔断
    HIGH_LATENCY_DEVIATION = "HIGH_LATENCY_DEVIATION"  # 耗时统计异常波动 (高偏离 σ)
    NORMAL = "NORMAL"


@dataclass
class AnomalyClusterItem:
    cluster_id: str
    service_name: str
    operation_name: str
    pattern: AnomalyPattern
    occurrences_count: int
    avg_duration_ms: float
    p95_duration_ms: float
    max_duration_ms: float
    deviation_sigma: float  # 偏离倍数 (Z-Score)
    error_ratio_pct: float
    impact_score: float  # 危害度综合得分
    root_cause_explanation: str
    actionable_recommendations: list[str]
    sample_trace_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "pattern": self.pattern.value,
            "occurrences_count": self.occurrences_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "p95_duration_ms": round(self.p95_duration_ms, 2),
            "max_duration_ms": round(self.max_duration_ms, 2),
            "deviation_sigma": round(self.deviation_sigma, 2),
            "error_ratio_pct": round(self.error_ratio_pct, 2),
            "impact_score": round(self.impact_score, 2),
            "root_cause_explanation": self.root_cause_explanation,
            "actionable_recommendations": self.actionable_recommendations,
            "sample_trace_ids": self.sample_trace_ids[:5],
        }


@dataclass
class TraceAnomalyClusterReport:
    total_spans_analyzed: int
    total_anomalies_detected: int
    clusters_count: int
    clusters: list[AnomalyClusterItem]
    verdict_summary: str
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spans_analyzed": self.total_spans_analyzed,
            "total_anomalies_detected": self.total_anomalies_detected,
            "clusters_count": self.clusters_count,
            "clusters": [c.to_dict() for c in self.clusters],
            "verdict_summary": self.verdict_summary,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


def _detect_span_pattern(span: dict[str, Any], duration_ms: float, slow_threshold_ms: float) -> AnomalyPattern:
    """判定单个 Span 的异常模式归属。"""
    attrs = span.get("attributes", {})
    status_code = str(span.get("status_code", "OK")).upper()
    status_msg = str(span.get("status_message", "")).lower()

    # 1. 数据库
    if "db.system" in attrs or "db.statement" in attrs or "sql" in span.get("name", "").lower():
        if duration_ms >= 50.0:
            return AnomalyPattern.SLOW_DATABASE_QUERY

    # 2. 超时
    if "timeout" in status_msg or attrs.get("http.status_code") in (504, 408) or duration_ms >= 3000.0:
        return AnomalyPattern.TIMEOUT_BREACH

    # 3. 下游 5xx
    http_code = attrs.get("http.status_code")
    if (http_code and int(http_code) >= 500) or status_code == "ERROR":
        return AnomalyPattern.DOWNSTREAM_SERVICE_5XX

    # 4. 熔断降级
    if attrs.get("circuit_breaker.state") == "OPEN" or "fallback" in attrs:
        return AnomalyPattern.CIRCUIT_BREAKER_OPEN

    # 5. 高耗时偏离
    if duration_ms >= slow_threshold_ms:
        return AnomalyPattern.HIGH_LATENCY_DEVIATION

    return AnomalyPattern.NORMAL


def cluster_trace_anomalies(
    spans: list[dict[str, Any]],
    slow_threshold_ms: float = 200.0,
) -> TraceAnomalyClusterReport:
    """对跨 Trace 的 Span 集合执行高频慢调用与异常波动聚类。"""
    if not spans:
        return TraceAnomalyClusterReport(
            total_spans_analyzed=0,
            total_anomalies_detected=0,
            clusters_count=0,
            clusters=[],
            verdict_summary="无 Span 数据待分析",
        )

    # 收集全部 span 耗时用于计算全局均值和基准方差
    all_durations = [float(s.get("duration_ms", 0.0)) for s in spans]
    global_mean = sum(all_durations) / len(all_durations) if all_durations else 0.0
    global_variance = (
        sum((d - global_mean) ** 2 for d in all_durations) / len(all_durations) if len(all_durations) > 1 else 1.0
    )
    global_std = math.sqrt(max(1.0, global_variance))

    # 聚类桶: key -> list[span]
    buckets: dict[tuple[str, str, AnomalyPattern], list[dict[str, Any]]] = {}
    total_anomalies = 0

    for s in spans:
        dur = float(s.get("duration_ms", 0.0))
        pattern = _detect_span_pattern(s, dur, slow_threshold_ms)

        if pattern == AnomalyPattern.NORMAL:
            continue

        total_anomalies += 1
        service = str(s.get("service_name", "unknown-service"))
        op_name = str(s.get("name", "operation"))

        bucket_key = (service, op_name, pattern)
        if bucket_key not in buckets:
            buckets[bucket_key] = []
        buckets[bucket_key].append(s)

    cluster_items: list[AnomalyClusterItem] = []

    for (service, op_name, pattern), bucket_spans in buckets.items():
        durations = sorted([float(s.get("duration_ms", 0.0)) for s in bucket_spans])
        count = len(durations)

        avg_dur = sum(durations) / count
        max_dur = durations[-1]
        p95_idx = int(math.ceil(0.95 * count)) - 1
        p95_dur = durations[min(p95_idx, count - 1)]

        # 计算该聚类相对全局均值的偏离度 Z-score (偏离几个 σ)
        deviation_sigma = max(0.0, (avg_dur - global_mean) / global_std)

        err_count = sum(
            1
            for s in bucket_spans
            if str(s.get("status_code", "")).upper() == "ERROR"
            or int(s.get("attributes", {}).get("http.status_code", 200)) >= 500
        )
        error_ratio = (err_count / count * 100.0) if count > 0 else 0.0

        # 危害度评分: 次数 * (平均耗时 / 阈值) * 错误率加成
        impact_score = count * (avg_dur / max(1.0, slow_threshold_ms)) * (1.0 + error_ratio / 100.0)

        # 根因推导与加固建议
        root_cause = ""
        recommendations = []

        if pattern == AnomalyPattern.SLOW_DATABASE_QUERY:
            root_cause = f"[{service}] 的 [{op_name}] 频繁触发慢 SQL 查询，平均时延 {round(avg_dur, 2)}ms。"
            recommendations = [
                "为查询字段添加复合索引，避免全表扫描",
                "对高频读操作引入 Redis 缓存或本地热点缓存",
            ]
        elif pattern == AnomalyPattern.TIMEOUT_BREACH:
            root_cause = f"[{service}] 的 [{op_name}] 遭遇上游/网络超时截断，最大耗时高达 {round(max_dur, 2)}ms。"
            recommendations = [
                "适当调大 HTTP/RPC 客户端超时时间或建立熔断超时回退策略",
                "检查网络连通性或排查重试风暴",
            ]
        elif pattern == AnomalyPattern.DOWNSTREAM_SERVICE_5XX:
            root_cause = f"[{service}] 调用发生服务端 5xx 错误，错误率高达 {round(error_ratio, 1)}%。"
            recommendations = [
                "检查下游微服务容器健康探针与错误日志",
                "对非关键业务依赖配置 Mock 降级兜底",
            ]
        elif pattern == AnomalyPattern.CIRCUIT_BREAKER_OPEN:
            root_cause = f"[{service}] 断路器处于 OPEN 状态，直接触发降级响应。"
            recommendations = [
                "排查下游依赖恢复状态并等待半开探针自愈",
            ]
        else:
            root_cause = f"[{service}] 的 [{op_name}] 出现统计显著的高时延偏离 (偏离度 {round(deviation_sigma, 1)}σ)。"
            recommendations = [
                "排查垃圾回收 (GC Stop-The-World) 或高并发线程竞争锁等待",
            ]

        sample_tids = list({str(s.get("trace_id", "")) for s in bucket_spans if s.get("trace_id")})

        cluster_id = f"cls_{service}_{op_name}_{pattern.value}".replace(" ", "_").replace("/", "_")

        cluster_items.append(
            AnomalyClusterItem(
                cluster_id=cluster_id,
                service_name=service,
                operation_name=op_name,
                pattern=pattern,
                occurrences_count=count,
                avg_duration_ms=avg_dur,
                p95_duration_ms=p95_dur,
                max_duration_ms=max_dur,
                deviation_sigma=deviation_sigma,
                error_ratio_pct=error_ratio,
                impact_score=impact_score,
                root_cause_explanation=root_cause,
                actionable_recommendations=recommendations,
                sample_trace_ids=sample_tids,
            )
        )

    # 按危害度降序
    cluster_items.sort(key=lambda c: c.impact_score, reverse=True)

    if cluster_items:
        top = cluster_items[0]
        verdict = (
            f"共检出 {len(cluster_items)} 个异常慢调用聚类簇，累计异常频次 {total_anomalies} 次。"
            f"首要危害簇为 [{top.service_name}] 的 [{top.operation_name}] "
            f"({top.pattern.value}，危害度得分 {round(top.impact_score, 1)}，平均耗时 {round(top.avg_duration_ms, 2)}ms)。"
        )
    else:
        verdict = "全链路无显著慢调用或异常波动，性能表现稳健。"

    return TraceAnomalyClusterReport(
        total_spans_analyzed=len(spans),
        total_anomalies_detected=total_anomalies,
        clusters_count=len(cluster_items),
        clusters=cluster_items,
        verdict_summary=verdict,
    )


def diagnose_telemetry_traces(slow_threshold_ms: float = 200.0) -> TraceAnomalyClusterReport:
    """直接对中继仓库中已采集的全部分布式 Trace 执行聚类诊断。"""
    flat_spans: list[dict[str, Any]] = []

    for tid in telemetry_relay._SPAN_STORE:
        tree = reconstruct_trace_tree(tid)
        if not tree:
            continue

        def _walk(node: Any) -> None:
            flat_spans.append(node.span.to_dict())
            for ch in node.children:
                _walk(ch)

        for root_node in tree.root_nodes:
            _walk(root_node)

    return cluster_trace_anomalies(flat_spans, slow_threshold_ms)
