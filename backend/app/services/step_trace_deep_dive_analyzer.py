"""异常步骤调用链深潜下钻与首因归因器服务 (T2.2)

当自动化测试步骤失败(4xx/5xx/RPC 异常/断言未通过/超时)时,
根据 TraceID 关联检索全链路微服务 Span,
自动执行拓扑回溯并定位:
1. 首因故障微服务与首因 Span (Root Cause Span);
2. 关联慢 SQL 查询 (Slow Database Query) 与执行耗时;
3. 异常类名 (Exception Class)、错误消息与堆栈指纹;
4. 智能归因类型分类与排障处置建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


class FailureAttributionType(str, Enum):
    DOWNSTREAM_SERVICE_ERROR = "DOWNSTREAM_SERVICE_ERROR"
    SLOW_DATABASE_QUERY = "SLOW_DATABASE_QUERY"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    ASSERTION_MISMATCH = "ASSERTION_MISMATCH"
    AUTH_CREDENTIAL_ERROR = "AUTH_CREDENTIAL_ERROR"
    UNKNOWN_SYSTEM_ERROR = "UNKNOWN_SYSTEM_ERROR"


@dataclass
class SlowQueryDetail:
    span_id: str
    service_name: str
    db_system: str
    duration_ms: float
    statement: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "service_name": self.service_name,
            "db_system": self.db_system,
            "duration_ms": round(self.duration_ms, 2),
            "statement": self.statement,
        }


@dataclass
class RootCauseDiagnosis:
    trace_id: str
    step_name: str
    step_status: str
    attribution_type: FailureAttributionType
    root_cause_service: str
    root_cause_span_id: str
    root_cause_span_name: str
    error_message: str
    stack_trace: str
    slow_queries: List[SlowQueryDetail] = field(default_factory=list)
    total_spans_analyzed: int = 0
    error_spans_count: int = 0
    diagnosis_summary: str = ""
    suggested_action: str = ""
    diagnosed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "step_name": self.step_name,
            "step_status": self.step_status,
            "attribution_type": self.attribution_type.value,
            "root_cause_service": self.root_cause_service,
            "root_cause_span_id": self.root_cause_span_id,
            "root_cause_span_name": self.root_cause_span_name,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "slow_queries": [q.to_dict() for q in self.slow_queries],
            "total_spans_analyzed": self.total_spans_analyzed,
            "error_spans_count": self.error_spans_count,
            "diagnosis_summary": self.diagnosis_summary,
            "suggested_action": self.suggested_action,
            "diagnosed_at": self.diagnosed_at,
        }


# 全局轻量级诊断历史记录
_DIAGNOSIS_HISTORY: List[RootCauseDiagnosis] = []


def clear_diagnosis_history() -> None:
    _DIAGNOSIS_HISTORY.clear()


def list_diagnosis_history(limit: int = 50) -> List[Dict[str, Any]]:
    return [d.to_dict() for d in reversed(_DIAGNOSIS_HISTORY[-limit:])]


def deep_dive_analyze_trace(
    step_context: Dict[str, Any],
    spans: List[Dict[str, Any]],
    slow_query_threshold_ms: float = 150.0,
) -> RootCauseDiagnosis:
    """对失败测试步骤所绑定的调用链执行深潜分析与首因归因定位"""
    trace_id = str(step_context.get("trace_id", "trace_unknown"))
    step_name = str(step_context.get("name", "未命名测试步骤"))
    step_status = str(step_context.get("status", "FAILED"))
    step_error = str(step_context.get("error_message", ""))

    total_spans = len(spans)
    error_spans: List[Dict[str, Any]] = []
    slow_queries: List[SlowQueryDetail] = []

    for s in spans:
        status_info = s.get("status", {})
        code = str(status_info.get("code", "")).upper()
        http_code = int(s.get("attributes", {}).get("http.status_code", 200))

        is_error = code in ("STATUS_CODE_ERROR", "ERROR", "2") or http_code >= 400 or bool(s.get("error"))
        if is_error:
            error_spans.append(s)

        # 检查是否为数据库慢查询 Span
        db_system = s.get("attributes", {}).get("db.system", "")
        db_statement = s.get("attributes", {}).get("db.statement", "")
        duration = float(s.get("duration_ms", 0.0))
        if (db_system or db_statement) and duration >= slow_query_threshold_ms:
            slow_queries.append(
                SlowQueryDetail(
                    span_id=str(s.get("span_id", "")),
                    service_name=str(s.get("service_name", "db-service")),
                    db_system=str(db_system or "relational-db"),
                    duration_ms=duration,
                    statement=str(db_statement or "SELECT ..."),
                )
            )

    # 判定首因 Span (Root Cause Span)：优先拓扑中最深/子节点中的第一个报错 Span
    root_cause_service = "client-step"
    root_cause_span_id = str(step_context.get("span_id", "step_root"))
    root_cause_span_name = step_name
    err_msg = step_error
    stack_trace = ""
    attr_type = FailureAttributionType.ASSERTION_MISMATCH

    if error_spans:
        # 按时间倒序或具有 parent_span_id 的下游微服务寻找最底层 Span
        leaf_error = error_spans[-1]
        root_cause_service = str(leaf_error.get("service_name", "downstream-service"))
        root_cause_span_id = str(leaf_error.get("span_id", ""))
        root_cause_span_name = str(leaf_error.get("name", "error_operation"))

        # 提取报错信息与堆栈
        attrs = leaf_error.get("attributes", {})
        err_msg = str(
            leaf_error.get("status", {}).get("message")
            or attrs.get("exception.message")
            or attrs.get("error.message")
            or err_msg
            or "微服务抛出非预期内部异常"
        )
        stack_trace = str(attrs.get("exception.stacktrace") or "")

        # 智能归因判定
        http_code = int(attrs.get("http.status_code", 0))
        if http_code in (401, 403):
            attr_type = FailureAttributionType.AUTH_CREDENTIAL_ERROR
        elif "timeout" in err_msg.lower() or "deadline" in err_msg.lower() or http_code == 504:
            attr_type = FailureAttributionType.NETWORK_TIMEOUT
        else:
            attr_type = FailureAttributionType.DOWNSTREAM_SERVICE_ERROR
    elif slow_queries:
        attr_type = FailureAttributionType.SLOW_DATABASE_QUERY
        worst_db = max(slow_queries, key=lambda q: q.duration_ms)
        root_cause_service = worst_db.service_name
        root_cause_span_id = worst_db.span_id
        root_cause_span_name = f"SQL: {worst_db.statement[:30]}"
        err_msg = f"数据库查询耗时过长 ({worst_db.duration_ms}ms >= 阈值 {slow_query_threshold_ms}ms) 引发步骤级响应超时或劣化"
    elif "assertion" in step_error.lower() or "assert" in step_error.lower():
        attr_type = FailureAttributionType.ASSERTION_MISMATCH
        err_msg = step_error
    else:
        attr_type = FailureAttributionType.UNKNOWN_SYSTEM_ERROR
        err_msg = step_error or "未捕获明确的底层报错跨度"

    # 生成排障处置建议
    if attr_type == FailureAttributionType.DOWNSTREAM_SERVICE_ERROR:
        diagnosis_summary = (
            f"步骤在调用链最深层微服务 [{root_cause_service}] 的跨度 [{root_cause_span_name}] 发生真实业务报错。"
        )
        suggested_action = f"请检查下游微服务 [{root_cause_service}] 日志与配置，排查错误原因: {err_msg}。"
    elif attr_type == FailureAttributionType.SLOW_DATABASE_QUERY:
        diagnosis_summary = f"步骤延迟主要消耗在微服务 [{root_cause_service}] 的慢 SQL 查询上。"
        suggested_action = "请为目标数据表添加必要索引，或优化 SQL 条件减少全表扫描。"
    elif attr_type == FailureAttributionType.NETWORK_TIMEOUT:
        diagnosis_summary = f"步骤因微服务间网络握手或执行超时中断 (Span: {root_cause_span_name})。"
        suggested_action = "请检查网络网关限流策略、连接池大小或调大 RPC 超时时间。"
    elif attr_type == FailureAttributionType.AUTH_CREDENTIAL_ERROR:
        diagnosis_summary = "请求被下游微服务鉴权拦截 (HTTP 401/403)。"
        suggested_action = "请检查用例配置的全局 Token、Cookie 或签名鉴权参数是否过期。"
    elif attr_type == FailureAttributionType.ASSERTION_MISMATCH:
        diagnosis_summary = "下游微服务调用链路正常，但返回数据不符合用例期望断言规则。"
        suggested_action = "请核验测试用例断言规则是否契合当前版本业务字段变更。"
    else:
        diagnosis_summary = "步骤未通过，但未探针到显式服务层报错。"
        suggested_action = "请开启更细粒度分布式追踪采样以获取深入跨度数据。"

    diagnosis = RootCauseDiagnosis(
        trace_id=trace_id,
        step_name=step_name,
        step_status=step_status,
        attribution_type=attr_type,
        root_cause_service=root_cause_service,
        root_cause_span_id=root_cause_span_id,
        root_cause_span_name=root_cause_span_name,
        error_message=err_msg,
        stack_trace=stack_trace,
        slow_queries=slow_queries,
        total_spans_analyzed=total_spans,
        error_spans_count=len(error_spans),
        diagnosis_summary=diagnosis_summary,
        suggested_action=suggested_action,
    )
    _DIAGNOSIS_HISTORY.append(diagnosis)
    return diagnosis
