"""任务调度风暴熔断防雪崩看门狗服务 (T4.1)

防范瞬时超大规模高并发任务涌入或故障重试引发的真机集群雪崩:
1. 突发速率平滑令牌桶 (Token Bucket Rate Limiter: 控制峰值突发调度速率);
2. 连续失败熔断断路器 (Circuit Breaker: CLOSED -> OPEN -> HALF_OPEN 快速失败保护);
3. 指数退避与全抖动打散算法 (Full Jitter Exponential Backoff: 消除请求共振);
4. 调度风暴违规审计与实时熔断状态管理。
"""

from __future__ import annotations

import enum
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class StormGuardState(str, enum.Enum):
    CLOSED = "CLOSED"  # 正常工作状态，允许调度
    OPEN = "OPEN"  # 熔断开启状态，快速失败阻断
    HALF_OPEN = "HALF_OPEN"  # 半开试探状态，允许少量探测流量


class StormGuardVerdict(str, enum.Enum):
    ALLOW = "ALLOW"  # 允许派发调度
    RATE_LIMITED = "RATE_LIMITED"  # 触发突发令牌桶限流
    CIRCUIT_TRIPPED = "CIRCUIT_TRIPPED"  # 触发熔断断路阻断


@dataclass
class StormGuardConfig:
    max_tokens: float = 30.0  # 令牌桶最大突发容量
    refill_rate_per_sec: float = 10.0  # 令牌填充速率 (个/秒)
    consecutive_failure_threshold: int = 5  # 连续失败熔断阈值
    failure_rate_threshold: float = 0.60  # 失败率阈值 (10秒滑动窗口)
    circuit_break_duration_sec: float = 15.0  # 熔断冷却时间 (秒)
    half_open_success_threshold: int = 2  # 半开状态成功试探转 CLOSED 阈值


@dataclass
class StormGuardStatus:
    state: StormGuardState
    available_tokens: float
    consecutive_failures: int
    recent_total_requests: int
    recent_failed_requests: int
    failure_rate: float
    last_state_change: str
    active_circuit_breaker: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "available_tokens": round(self.available_tokens, 2),
            "consecutive_failures": self.consecutive_failures,
            "recent_total_requests": self.recent_total_requests,
            "recent_failed_requests": self.recent_failed_requests,
            "failure_rate": round(self.failure_rate, 4),
            "last_state_change": self.last_state_change,
            "active_circuit_breaker": self.active_circuit_breaker,
        }


# 运行时单例状态
_CURRENT_STATE = StormGuardState.CLOSED
_TOKENS = 30.0
_LAST_REFILL_TIME = time.perf_counter()
_CONSECUTIVE_FAILURES = 0
_RECENT_WINDOW_REQUESTS: List[Tuple[float, bool]] = []  # (timestamp, is_success)
_OPENED_AT: Optional[float] = None
_HALF_OPEN_SUCCESSES = 0
_GUARD_EVENTS_STORE: List[Dict[str, Any]] = []


def clear_storm_guard_state() -> None:
    """清空风暴看门狗状态（测试夹具使用）"""
    global _CURRENT_STATE, _TOKENS, _LAST_REFILL_TIME, _CONSECUTIVE_FAILURES
    global _RECENT_WINDOW_REQUESTS, _OPENED_AT, _HALF_OPEN_SUCCESSES
    _CURRENT_STATE = StormGuardState.CLOSED
    _TOKENS = 30.0
    _LAST_REFILL_TIME = time.perf_counter()
    _CONSECUTIVE_FAILURES = 0
    _RECENT_WINDOW_REQUESTS.clear()
    _OPENED_AT = None
    _HALF_OPEN_SUCCESSES = 0
    _GUARD_EVENTS_STORE.clear()


def _refill_tokens(config: StormGuardConfig) -> None:
    """根据时间流逝填充令牌"""
    global _TOKENS, _LAST_REFILL_TIME
    now = time.perf_counter()
    elapsed = now - _LAST_REFILL_TIME
    _LAST_REFILL_TIME = now
    _TOKENS = min(config.max_tokens, _TOKENS + elapsed * config.refill_rate_per_sec)


def _clean_sliding_window(window_sec: float = 10.0) -> None:
    """清理滑动窗口中过期的请求记录"""
    global _RECENT_WINDOW_REQUESTS
    now = time.perf_counter()
    _RECENT_WINDOW_REQUESTS = [(ts, ok) for ts, ok in _RECENT_WINDOW_REQUESTS if now - ts <= window_sec]


def calculate_jittered_backoff(retry_count: int, base_delay_ms: float = 200.0, max_delay_ms: float = 5000.0) -> float:
    """计算带全抖动的指数退避时间（消除并发共振）

    Full Jitter 算法: delay = random.uniform(0, min(max_delay, base * 2^retry))
    """
    exp_cap = min(max_delay_ms, base_delay_ms * (2 ** min(retry_count, 6)))
    return round(random.uniform(0.0, exp_cap), 2)


def evaluate_dispatch_storm_protection(
    task_id: str,
    config: Optional[StormGuardConfig] = None,
) -> Tuple[StormGuardVerdict, str]:
    """在派发调度前进行风暴防护审查，判定是否允许放行"""
    global _CURRENT_STATE, _OPENED_AT, _TOKENS, _HALF_OPEN_SUCCESSES
    cfg = config or StormGuardConfig()

    now = time.perf_counter()

    # 1. 断路器状态机转移检查
    if _CURRENT_STATE == StormGuardState.OPEN:
        if _OPENED_AT and (now - _OPENED_AT >= cfg.circuit_break_duration_sec):
            # 冷却时间到，转入 HALF_OPEN 半开试探
            _CURRENT_STATE = StormGuardState.HALF_OPEN
            _HALF_OPEN_SUCCESSES = 0
        else:
            remaining = round(cfg.circuit_break_duration_sec - (now - (_OPENED_AT or now)), 1)
            reason = f"风暴熔断断路器处于 OPEN 状态，快速失败阻断调度，剩余冷却时间: {max(0.0, remaining)}s"
            _record_guard_event(task_id, StormGuardVerdict.CIRCUIT_TRIPPED, reason)
            return StormGuardVerdict.CIRCUIT_TRIPPED, reason

    # 2. 令牌桶限流检查
    _refill_tokens(cfg)
    if _TOKENS < 1.0:
        reason = f"突发调度速率过高，当前可用令牌 ({round(_TOKENS, 1)} < 1.0)，触发限流削峰保护"
        _record_guard_event(task_id, StormGuardVerdict.RATE_LIMITED, reason)
        return StormGuardVerdict.RATE_LIMITED, reason

    # 消费 1 个令牌
    _TOKENS -= 1.0

    return StormGuardVerdict.ALLOW, "通过调度风暴安全审查，正常放行"


def record_dispatch_outcome(is_success: bool, config: Optional[StormGuardConfig] = None) -> None:
    """反馈单次调度的执行结果（成功或失败），用于驱动断路器自适应切换"""
    global _CONSECUTIVE_FAILURES, _CURRENT_STATE, _OPENED_AT, _HALF_OPEN_SUCCESSES
    cfg = config or StormGuardConfig()
    now = time.perf_counter()

    _RECENT_WINDOW_REQUESTS.append((now, is_success))
    _clean_sliding_window(10.0)

    if is_success:
        _CONSECUTIVE_FAILURES = 0
        if _CURRENT_STATE == StormGuardState.HALF_OPEN:
            _HALF_OPEN_SUCCESSES += 1
            if _HALF_OPEN_SUCCESSES >= cfg.half_open_success_threshold:
                _CURRENT_STATE = StormGuardState.CLOSED
                _OPENED_AT = None
    else:
        _CONSECUTIVE_FAILURES += 1

        # 检查是否满足熔断开启条件
        total = len(_RECENT_WINDOW_REQUESTS)
        fails = sum(1 for _, ok in _RECENT_WINDOW_REQUESTS if not ok)
        fail_rate = (fails / total) if total >= 5 else 0.0

        if _CONSECUTIVE_FAILURES >= cfg.consecutive_failure_threshold or fail_rate >= cfg.failure_rate_threshold:
            _CURRENT_STATE = StormGuardState.OPEN
            _OPENED_AT = now


def get_storm_guard_status() -> StormGuardStatus:
    """获取当前风暴看门狗运行状态快照"""
    _clean_sliding_window(10.0)
    total = len(_RECENT_WINDOW_REQUESTS)
    fails = sum(1 for _, ok in _RECENT_WINDOW_REQUESTS if not ok)
    fail_rate = (fails / total) if total > 0 else 0.0

    return StormGuardStatus(
        state=_CURRENT_STATE,
        available_tokens=_TOKENS,
        consecutive_failures=_CONSECUTIVE_FAILURES,
        recent_total_requests=total,
        recent_failed_requests=fails,
        failure_rate=fail_rate,
        last_state_change=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        active_circuit_breaker=_CURRENT_STATE == StormGuardState.OPEN,
    )


def reset_circuit_breaker() -> None:
    """手动复位熔断断路器至正常 CLOSED 状态"""
    global _CURRENT_STATE, _CONSECUTIVE_FAILURES, _OPENED_AT, _HALF_OPEN_SUCCESSES, _TOKENS
    _CURRENT_STATE = StormGuardState.CLOSED
    _CONSECUTIVE_FAILURES = 0
    _OPENED_AT = None
    _HALF_OPEN_SUCCESSES = 0
    _TOKENS = 30.0


def _record_guard_event(task_id: str, verdict: StormGuardVerdict, reason: str) -> None:
    _GUARD_EVENTS_STORE.append(
        {
            "event_id": f"sgev_{uuid.uuid4().hex[:8]}",
            "task_id": task_id,
            "verdict": verdict.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


def list_guard_interceptions(limit: int = 50) -> List[Dict[str, Any]]:
    """查询近期风暴拦截审计事件"""
    return _GUARD_EVENTS_STORE[-limit:]
