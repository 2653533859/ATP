"""移动端 CPU / 内存 / FPS / 网络流量实时时序采样与卡顿泄露诊断服务 (D3.1).

支持在自动化测试执行过程中对 Android 设备应用的多维性能数据进行实时高频采样，
采用线性回归斜率智能检测内存泄露趋势，结合帧率与丢帧分析智能标记 Jank 页面卡顿异常。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSamplePoint:
    timestamp_sec: float
    cpu_app_pct: float
    cpu_total_pct: float
    memory_pss_mb: float
    memory_native_heap_mb: float = 0.0
    memory_dalvik_heap_mb: float = 0.0
    fps: float = 60.0
    jank_count: int = 0
    net_tx_kbps: float = 0.0
    net_rx_kbps: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_sec": round(self.timestamp_sec, 2),
            "cpu_app_pct": round(self.cpu_app_pct, 2),
            "cpu_total_pct": round(self.cpu_total_pct, 2),
            "memory_pss_mb": round(self.memory_pss_mb, 2),
            "memory_native_heap_mb": round(self.memory_native_heap_mb, 2),
            "memory_dalvik_heap_mb": round(self.memory_dalvik_heap_mb, 2),
            "fps": round(self.fps, 1),
            "jank_count": self.jank_count,
            "net_tx_kbps": round(self.net_tx_kbps, 2),
            "net_rx_kbps": round(self.net_rx_kbps, 2),
        }


@dataclass
class MobilePerfSessionConfig:
    session_id: str
    device_serial: str
    package_name: str
    sample_interval_sec: float = 1.0
    jank_threshold_ms: float = 16.67
    big_jank_threshold_ms: float = 100.0


@dataclass
class DiagnosticAnomaly:
    anomaly_type: str  # MEMORY_LEAK_WARNING | HIGH_CPU_ALERT | JANK_FRAME_DROP
    severity: str  # critical | warning | info
    timestamp_sec: float
    metric_name: str
    metric_value: float
    threshold: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "timestamp_sec": round(self.timestamp_sec, 2),
            "metric_name": self.metric_name,
            "metric_value": round(self.metric_value, 2),
            "threshold": round(self.threshold, 2),
            "description": self.description,
        }


@dataclass
class MobilePerfSessionReport:
    session_id: str
    device_serial: str
    package_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    samples: list[PerformanceSamplePoint] = field(default_factory=list)
    anomalies: list[DiagnosticAnomaly] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def total_samples_count(self) -> int:
        return len(self.samples)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "device_serial": self.device_serial,
            "package_name": self.package_name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "total_samples_count": len(self.samples),
            "summary": self.summary,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "samples_preview": [s.to_dict() for s in self.samples[:50]],  # 预览最新50个点
        }


# 内存性能采样会话仓库
_PERF_SESSIONS: dict[str, MobilePerfSessionReport] = {}


def _calculate_linear_regression_slope(x_vals: list[float], y_vals: list[float]) -> float:
    """计算一维数据线性回归斜率（用于衡量内存增长趋势 MB/min）。"""
    n = len(x_vals)
    if n < 2:
        return 0.0

    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xx = sum(x * x for x in x_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))

    denominator = n * sum_xx - sum_x * sum_x
    if abs(denominator) < 1e-6:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return slope * 60.0  # 转换为 MB/min


def _analyze_session_diagnostics(session: MobilePerfSessionReport) -> None:
    """对已采集的时序性能点执行深度智能诊断分析。"""
    samples = session.samples
    if not samples:
        session.summary = {"empty": True}
        return

    # 1. 基础极值与均值统计
    cpu_app_vals = [s.cpu_app_pct for s in samples]
    memory_pss_vals = [s.memory_pss_mb for s in samples]
    fps_vals = [s.fps for s in samples]
    jank_counts = [s.jank_count for s in samples]

    cpu_app_avg = sum(cpu_app_vals) / len(cpu_app_vals)
    cpu_app_max = max(cpu_app_vals)
    mem_pss_max = max(memory_pss_vals)
    fps_avg = sum(fps_vals) / len(fps_vals)
    total_janks = sum(jank_counts)

    # 2. 内存增长斜率判定 (Memory Leak Trend)
    time_offsets = [s.timestamp_sec - samples[0].timestamp_sec for s in samples]
    mem_slope = _calculate_linear_regression_slope(time_offsets, memory_pss_vals)

    anomalies: list[DiagnosticAnomaly] = []

    # 判定内存泄露：持续增长斜率 > 5.0 MB/min 且样本点数 ≥ 5
    if len(samples) >= 5 and mem_slope > 5.0:
        anomalies.append(
            DiagnosticAnomaly(
                anomaly_type="MEMORY_LEAK_WARNING",
                severity="critical" if mem_slope > 15.0 else "warning",
                timestamp_sec=samples[-1].timestamp_sec,
                metric_name="memory_growth_slope_mb_per_min",
                metric_value=mem_slope,
                threshold=5.0,
                description=f"检测到应用物理内存 (PSS) 呈现线性单调持续增长趋势 (斜率: {mem_slope:.2f} MB/min)，疑似存在内存泄露！",
            )
        )

    # 判定高 CPU 占用
    if cpu_app_avg > 75.0:
        anomalies.append(
            DiagnosticAnomaly(
                anomaly_type="HIGH_CPU_ALERT",
                severity="warning",
                timestamp_sec=samples[0].timestamp_sec,
                metric_name="cpu_app_avg",
                metric_value=cpu_app_avg,
                threshold=75.0,
                description=f"应用平均 CPU 占用率达 {cpu_app_avg:.1f}%，突破 75% 性能警戒线",
            )
        )

    # 判定渲染卡顿与严重掉帧
    if fps_avg < 40.0 or total_janks > 10:
        anomalies.append(
            DiagnosticAnomaly(
                anomaly_type="JANK_FRAME_DROP",
                severity="critical" if fps_avg < 30.0 else "warning",
                timestamp_sec=samples[0].timestamp_sec,
                metric_name="fps_avg",
                metric_value=fps_avg,
                threshold=40.0,
                description=f"应用平均渲染帧率仅 {fps_avg:.1f} FPS，累计捕获卡顿帧 {total_janks} 次，界面存在显著掉帧与操作迟滞",
            )
        )

    session.anomalies = anomalies
    session.summary = {
        "cpu_app_avg": round(cpu_app_avg, 2),
        "cpu_app_max": round(cpu_app_max, 2),
        "memory_pss_max": round(mem_pss_max, 2),
        "memory_growth_slope_mb_per_min": round(mem_slope, 2),
        "fps_avg": round(fps_avg, 1),
        "total_janks": total_janks,
        "anomalies_count": len(anomalies),
        "has_memory_leak": any(a.anomaly_type == "MEMORY_LEAK_WARNING" for a in anomalies),
        "has_jank_drops": any(a.anomaly_type == "JANK_FRAME_DROP" for a in anomalies),
    }


def start_perf_session(config: MobilePerfSessionConfig) -> MobilePerfSessionReport:
    """初始化并启动移动端性能时序采集会话。"""
    session = MobilePerfSessionReport(
        session_id=config.session_id,
        device_serial=config.device_serial,
        package_name=config.package_name,
        started_at=datetime.now(timezone.utc),
    )
    _PERF_SESSIONS[config.session_id] = session
    logger.info(
        "Started mobile perf session session_id=%s device=%s pkg=%s",
        config.session_id,
        config.device_serial,
        config.package_name,
    )
    return session


def record_perf_sample(session_id: str, sample: PerformanceSamplePoint) -> None:
    """向指定会话追加单个性能采样点。"""
    session = _PERF_SESSIONS.get(session_id)
    if not session:
        raise ValueError(f"性能会话不存在: {session_id}")
    session.samples.append(sample)


def record_perf_samples_batch(session_id: str, samples: list[PerformanceSamplePoint]) -> None:
    """向指定会话批量追加性能采样点。"""
    session = _PERF_SESSIONS.get(session_id)
    if not session:
        raise ValueError(f"性能会话不存在: {session_id}")
    session.samples.extend(samples)


def stop_perf_session(session_id: str) -> MobilePerfSessionReport:
    """停止采样会话并运行深度智能诊断算法。"""
    session = _PERF_SESSIONS.get(session_id)
    if not session:
        raise ValueError(f"性能会话不存在: {session_id}")

    session.ended_at = datetime.now(timezone.utc)
    _analyze_session_diagnostics(session)
    logger.info(
        "Stopped mobile perf session session_id=%s samples=%s anomalies=%s",
        session_id,
        len(session.samples),
        len(session.anomalies),
    )
    return session


def get_perf_session_report(session_id: str) -> MobilePerfSessionReport | None:
    """获取指定性能会话的完整诊断报告。"""
    return _PERF_SESSIONS.get(session_id)


def list_perf_sessions() -> list[MobilePerfSessionReport]:
    """查询全部已记录的移动端性能诊断会话。"""
    return list(_PERF_SESSIONS.values())


def reset_mobile_perf_registry() -> None:
    """供单元测试清理状态使用。"""
    _PERF_SESSIONS.clear()
