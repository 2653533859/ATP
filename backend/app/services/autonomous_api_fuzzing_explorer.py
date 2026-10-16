"""自主探索式 API 模糊变异与隐蔽缺陷深度探查器 (T3.3)。"""

from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FuzzMutationStrategy(str, Enum):
    """模糊变异策略分类。"""

    SQL_INJECTION_PROBE = "SQL_INJECTION_PROBE"
    XSS_HTML_PAYLOAD = "XSS_HTML_PAYLOAD"
    UNICODE_CONTROL_CHARS = "UNICODE_CONTROL_CHARS"
    NUMERIC_OVERFLOW = "NUMERIC_OVERFLOW"
    FORMAT_STRING_INJECTION = "FORMAT_STRING_INJECTION"
    TYPE_CONFUSION = "TYPE_CONFUSION"


class FuzzFlawType(str, Enum):
    """缺陷特征类型。"""

    UNHANDLED_SERVER_CRASH = "UNHANDLED_SERVER_CRASH"
    INJECTION_SECURITY_VULN = "INJECTION_SECURITY_VULN"
    PERFORMANCE_SPIKE_DOS = "PERFORMANCE_SPIKE_DOS"
    GRACEFUL_REJECTION = "GRACEFUL_REJECTION"


class FlawSeverity(str, Enum):
    """缺陷严重度等级。"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class FuzzingFlawFinding:
    """单条探查出的缺陷明细。"""

    flaw_id: str
    strategy: FuzzMutationStrategy
    flaw_type: FuzzFlawType
    severity: FlawSeverity
    mutated_key: str
    mutated_value: Any
    status_code: int
    response_excerpt: str
    reproduction_curl: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "flaw_id": self.flaw_id,
            "strategy": self.strategy.value,
            "flaw_type": self.flaw_type.value,
            "severity": self.severity.value,
            "mutated_key": self.mutated_key,
            "mutated_value": self.mutated_value,
            "status_code": self.status_code,
            "response_excerpt": self.response_excerpt,
            "reproduction_curl": self.reproduction_curl,
        }


@dataclass
class FuzzingExplorationSession:
    """探索式变异测试会话报告。"""

    session_id: str
    target_endpoint: str
    target_method: str
    total_mutations_count: int
    flaws_count: int
    critical_count: int
    high_count: int
    robustness_score_pct: float  # 健壮性得分 0~100%
    findings: list[FuzzingFlawFinding]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_endpoint": self.target_endpoint,
            "target_method": self.target_method,
            "total_mutations_count": self.total_mutations_count,
            "flaws_count": self.flaws_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "robustness_score_pct": round(self.robustness_score_pct, 1),
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at.isoformat(),
        }


# 全局探索会话仓库
_FUZZING_SESSIONS: dict[str, FuzzingExplorationSession] = {}

# 变异字典库
MUTATION_VECTORS: dict[FuzzMutationStrategy, list[Any]] = {
    FuzzMutationStrategy.SQL_INJECTION_PROBE: [
        "' OR '1'='1' --",
        "admin' UNION SELECT 1,2,3--",
        "'; DROP TABLE users; --",
    ],
    FuzzMutationStrategy.XSS_HTML_PAYLOAD: [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert(1)",
    ],
    FuzzMutationStrategy.UNICODE_CONTROL_CHARS: [
        "\x00\x00\x00\x00",
        "\r\n\r\nHTTP/1.1 200 OK",
        "\uffff\ufeff\u202e",
    ],
    FuzzMutationStrategy.NUMERIC_OVERFLOW: [
        9223372036854775808,
        -9223372036854775809,
        float("inf"),
    ],
    FuzzMutationStrategy.FORMAT_STRING_INJECTION: [
        "%s%s%s%s%s%n",
        "{{7*7}}",
        "${7*7}",
    ],
    FuzzMutationStrategy.TYPE_CONFUSION: [
        {"nested": "object_confusion"},
        [1, 2, 3, "array_confusion"],
        True,
    ],
}


def clear_fuzzing_store() -> None:
    """清空探索会话仓库（单测专用）。"""
    _FUZZING_SESSIONS.clear()


def _mock_execute_target_api(
    endpoint: str,
    method: str,
    payload: dict[str, Any],
) -> tuple[int, str, float]:
    """模拟向目标接口发送变异 Payload 并捕获状态码、响应体与耗时。"""
    _ = (endpoint, method)
    # 规则性探测模拟（真实环境对接真实 HTTP 发包）
    str_payload = json.dumps(payload, ensure_ascii=False)
    elapsed_ms = 45.0

    # 1. 模拟 SQL 注入引发 500 未捕获异常
    if "DROP TABLE" in str_payload:
        return (500, "InternalServerError: syntax error at or near 'DROP TABLE'", elapsed_ms)

    # 2. 模拟 超长/格式溢出
    if "%s%s%s" in str_payload:
        return (500, "SegmentationFault or Unhandled StringFormatError", elapsed_ms)

    # 3. 模拟 性能突增
    if "\uffff\ufeff" in str_payload:
        return (200, '{"code": 0, "message": "ok"}', 3500.0)

    # 4. 正常被参数校验拦截（标准防御）
    if "' OR '1'='1'" in str_payload or "<script>" in str_payload or "9223372036854775808" in str_payload:
        return (
            422,
            '{"detail": "validation error: input contains illegal characters or value out of bounds"}',
            elapsed_ms,
        )

    # 默认正常响应
    return (200, '{"code": 0, "message": "success"}', elapsed_ms)


def execute_fuzzing_exploration(
    endpoint: str,
    method: str = "POST",
    base_payload: dict[str, Any] | None = None,
    strategies: list[str] | None = None,
) -> FuzzingExplorationSession:
    """对目标接口执行多轮自主模糊变异测试。"""
    base = base_payload or {"username": "admin", "age": 25, "query": "default"}
    active_strategies = [FuzzMutationStrategy(s) for s in strategies] if strategies else list(FuzzMutationStrategy)

    findings: list[FuzzingFlawFinding] = []
    total_mutations = 0

    for key, _orig_val in base.items():
        for strat in active_strategies:
            vectors = MUTATION_VECTORS.get(strat, [])
            for vector in vectors:
                total_mutations += 1
                mutated_payload = copy.deepcopy(base)
                mutated_payload[key] = vector

                # 模拟发送变异请求
                status_code, resp_text, elapsed_ms = _mock_execute_target_api(
                    endpoint=endpoint,
                    method=method,
                    payload=mutated_payload,
                )

                curl_cmd = f"curl -X {method} '{endpoint}' -H 'Content-Type: application/json' -d '{json.dumps(mutated_payload)}'"

                # 判定是否存在缺陷
                if status_code >= 500:
                    flaw = FuzzingFlawFinding(
                        flaw_id=f"flaw_{uuid.uuid4().hex[:8]}",
                        strategy=strat,
                        flaw_type=FuzzFlawType.UNHANDLED_SERVER_CRASH,
                        severity=FlawSeverity.CRITICAL,
                        mutated_key=key,
                        mutated_value=vector if isinstance(vector, (str, int, float, bool)) else str(vector),
                        status_code=status_code,
                        response_excerpt=resp_text[:120],
                        reproduction_curl=curl_cmd,
                    )
                    findings.append(flaw)
                elif elapsed_ms >= 3000.0:
                    flaw = FuzzingFlawFinding(
                        flaw_id=f"flaw_{uuid.uuid4().hex[:8]}",
                        strategy=strat,
                        flaw_type=FuzzFlawType.PERFORMANCE_SPIKE_DOS,
                        severity=FlawSeverity.HIGH,
                        mutated_key=key,
                        mutated_value=vector if isinstance(vector, (str, int, float, bool)) else str(vector),
                        status_code=status_code,
                        response_excerpt=f"请求耗时异常飙升 ({elapsed_ms}ms)，疑似 ReDoS 或死循环",
                        reproduction_curl=curl_cmd,
                    )
                    findings.append(flaw)
                elif "syntax error" in resp_text.lower():
                    flaw = FuzzingFlawFinding(
                        flaw_id=f"flaw_{uuid.uuid4().hex[:8]}",
                        strategy=strat,
                        flaw_type=FuzzFlawType.INJECTION_SECURITY_VULN,
                        severity=FlawSeverity.CRITICAL,
                        mutated_key=key,
                        mutated_value=vector if isinstance(vector, (str, int, float, bool)) else str(vector),
                        status_code=status_code,
                        response_excerpt=resp_text[:120],
                        reproduction_curl=curl_cmd,
                    )
                    findings.append(flaw)

    crit_c = sum(1 for f in findings if f.severity == FlawSeverity.CRITICAL)
    high_c = sum(1 for f in findings if f.severity == FlawSeverity.HIGH)

    # 计算健壮性得分：100 - (CRITICAL * 30 + HIGH * 15)
    penalty = (crit_c * 30.0) + (high_c * 15.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    clean_ep = re.sub(r"[^a-zA-Z0-9_]", "_", endpoint).strip("_")
    session_id = f"fuzz_{clean_ep[:16]}_{int(now.timestamp())}"

    session = FuzzingExplorationSession(
        session_id=session_id,
        target_endpoint=endpoint,
        target_method=method,
        total_mutations_count=total_mutations,
        flaws_count=len(findings),
        critical_count=crit_c,
        high_count=high_c,
        robustness_score_pct=score,
        findings=findings,
        created_at=now,
    )
    _FUZZING_SESSIONS[session_id] = session
    return session


def get_fuzzing_session(session_id: str) -> FuzzingExplorationSession | None:
    """按 ID 查询探索会话。"""
    return _FUZZING_SESSIONS.get(session_id)


def list_fuzzing_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史探索会话列表。"""
    sessions = list(reversed(list(_FUZZING_SESSIONS.values())))
    return [s.to_dict() for s in sessions[:limit]]
