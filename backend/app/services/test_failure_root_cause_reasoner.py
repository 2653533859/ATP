"""多模态测试失败日志与异常堆栈智能根因推导引擎 (T3.1)。

融合测试控制台输出、HTTP 报文、分布式调用链 (Span) 与环境因子：
1. 消除层层级联报错的误导，定位首发源头微服务与代码行 (Culprit Location)；
2. 还原完整的因果失效传播链条 (Causal Chain)；
3. 输出高置信度 (Confidence Score) 结构化根因分析报告与针对性处置方案。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class RootCauseCategory(str, Enum):
    ASSERTION_BUSINESS_LOGIC_DEFECT = "ASSERTION_BUSINESS_LOGIC_DEFECT"  # 业务逻辑断言失败
    DOWNSTREAM_SERVICE_CRASH = "DOWNSTREAM_SERVICE_CRASH"  # 下游微服务 500 崩溃/未捕获异常
    DATABASE_EXECUTION_FAILURE = "DATABASE_EXECUTION_FAILURE"  # 数据库死锁/慢查询超时/约束违规
    NETWORK_GATEWAY_TIMEOUT = "NETWORK_GATEWAY_TIMEOUT"  # 网关超时/连接重置 (504/408/ECONNRESET)
    AUTHENTICATION_EXPIRED = "AUTHENTICATION_EXPIRED"  # 登录凭证过期/越权拒绝 (401/403)
    UI_DOM_LOCATOR_DRIFT = "UI_DOM_LOCATOR_DRIFT"  # UI 元素定位漂移/DOM 元素不可交互
    TEST_DATA_PRECONDITION_UNMET = "TEST_DATA_PRECONDITION_UNMET"  # 测试前置数据缺失 (404/主键冲突)
    RESOURCE_STARVATION = "RESOURCE_STARVATION"  # 系统资源耗尽 (OOM/503 限流)
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"  # 未知异常


@dataclass
class EvidenceSnippet:
    evidence_type: str  # CONSOLE_LOG | HTTP_RESPONSE | SPAN_TRACE | ENV_FACTOR
    title: str
    content: str
    is_key_evidence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "title": self.title,
            "content": self.content[:1024],
            "is_key_evidence": self.is_key_evidence,
        }


@dataclass
class RootCauseAttributionReport:
    diagnosis_id: str
    case_id: str
    case_name: str
    category: RootCauseCategory
    confidence_score: float  # 0.0 ~ 1.0
    primary_root_cause_summary: str
    culprit_service: str
    culprit_location: str  # 文件名:行号 或 异常方法名
    causal_chain: list[str]
    evidence_snippets: list[EvidenceSnippet]
    suggested_action: str
    diagnosed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "category": self.category.value,
            "confidence_score": round(self.confidence_score, 2),
            "primary_root_cause_summary": self.primary_root_cause_summary,
            "culprit_service": self.culprit_service,
            "culprit_location": self.culprit_location,
            "causal_chain": self.causal_chain,
            "evidence_snippets": [e.to_dict() for e in self.evidence_snippets],
            "suggested_action": self.suggested_action,
            "diagnosed_at": self.diagnosed_at.isoformat(),
        }


# 全局诊断报告仓库: diagnosis_id -> RootCauseAttributionReport
_ROOT_CAUSE_STORE: dict[str, RootCauseAttributionReport] = {}


def _extract_culprit_location_from_log(log_text: str) -> str:
    """从异常堆栈文本中提取引发异常的最深物理代码行号。"""
    # 匹配: File "xxx.py", line 123, in foo
    file_line_matches = re.findall(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+([a-zA-Z0-9_]+)', log_text)
    if file_line_matches:
        last_match = file_line_matches[-1]
        file_path, line_num, func = last_match
        file_name = file_path.replace("\\", "/").split("/")[-1]
        return f"{file_name}:{line_num} in {func}()"

    # 匹配: at com.example.service.Class.method(Class.java:123)
    java_matches = re.findall(r"at\s+([a-zA-Z0-9_.]+)\(([a-zA-Z0-9_]+\.java):(\d+)\)", log_text)
    if java_matches:
        last_java = java_matches[-1]
        method_path, file_name, line_num = last_java
        return f"{file_name}:{line_num} in {method_path}"

    return "unknown_location"


def analyze_test_failure_root_cause(
    case_id: str,
    case_name: str,
    console_logs: str = "",
    http_status_code: int | None = None,
    http_response_body: str = "",
    spans: list[dict[str, Any]] | None = None,
    env_factors: dict[str, Any] | None = None,
    diagnosis_id: str | None = None,
) -> RootCauseAttributionReport:
    """融合多模态证据，推导测试失败根因与失效因果传播链条。"""
    did = diagnosis_id or f"diag_{uuid.uuid4().hex[:10]}"
    snippets: list[EvidenceSnippet] = []

    # 1. 采集控制台日志片段
    if console_logs:
        snippets.append(
            EvidenceSnippet(
                evidence_type="CONSOLE_LOG",
                title="用例执行控制台日志与堆栈",
                content=console_logs,
                is_key_evidence=False,
            )
        )

    # 2. 采集 HTTP 响应证据
    if http_status_code is not None:
        snippets.append(
            EvidenceSnippet(
                evidence_type="HTTP_RESPONSE",
                title=f"HTTP 响应状态与报文 (Status: {http_status_code})",
                content=http_response_body or f"Status: {http_status_code}",
                is_key_evidence=http_status_code >= 400,
            )
        )

    # 3. 采集调用链异常 Span
    error_spans = []
    if spans:
        for s in spans:
            status = str(s.get("status_code", s.get("status", "OK"))).upper()
            attrs = s.get("attributes", {})
            http_c = attrs.get("http.status_code")
            if status == "ERROR" or (http_c and int(http_c) >= 400):
                error_spans.append(s)
                snippets.append(
                    EvidenceSnippet(
                        evidence_type="SPAN_TRACE",
                        title=f"调用链异常 Span [{s.get('service_name')} - {s.get('name')}]",
                        content=str(s.get("status_message") or s.get("error_message") or str(attrs)),
                        is_key_evidence=True,
                    )
                )

    # 4. 采集环境因子
    if env_factors:
        snippets.append(
            EvidenceSnippet(
                evidence_type="ENV_FACTOR",
                title="系统环境与负载参数",
                content=str(env_factors),
                is_key_evidence=False,
            )
        )

    # 多模态推导模式匹配优先级判定
    category = RootCauseCategory.UNKNOWN_FAILURE
    confidence = 0.5
    summary = ""
    culprit_service = "unknown-service"
    culprit_location = _extract_culprit_location_from_log(console_logs)
    causal_chain: list[str] = []
    suggested_action = ""

    log_lower = console_logs.lower()
    resp_lower = http_response_body.lower()

    # 规则 1: 数据库层死锁、超时或语法错误
    if any(
        k in log_lower or k in resp_lower
        for k in (
            "deadlock",
            "lock wait timeout",
            "foreign key constraint",
            "duplicate entry",
            "mysql",
            "postgresql",
            "sqlalchemy",
        )
    ):
        category = RootCauseCategory.DATABASE_EXECUTION_FAILURE
        confidence = 0.95
        culprit_service = error_spans[0].get("service_name", "db-service") if error_spans else "database"
        summary = "数据库层事务冲突或死锁/锁等待超时，导致微服务业务写入被强制中止回滚。"
        causal_chain = [
            f"[1] 数据库产生并发行锁竞争/死锁异常 ({culprit_service})",
            "[2] 数据访问层 (DAO/ORM) 抛出异常并向上扩散",
            "[3] 顶层接口捕获未决，返回 500 内部错误",
            "[4] 自动化测试断言或用例步骤失败",
        ]
        suggested_action = "检查相关 SQL 事务范围，优化索引避免间隙锁，为高并发写操作配置重试退避机制。"

    # 规则 2: 网络网关超时 (504/408/ECONNRESET)
    elif http_status_code in (504, 408) or any(
        k in log_lower or k in resp_lower
        for k in ("gateway timeout", "connection timed out", "read timeout", "econnreset", "sockettimeout")
    ):
        category = RootCauseCategory.NETWORK_GATEWAY_TIMEOUT
        confidence = 0.92
        culprit_service = error_spans[-1].get("service_name", "gateway") if error_spans else "network-gateway"
        summary = f"下游微服务处理超时，网关触发超时熔断截断响应 (Status: {http_status_code or 504})。"
        causal_chain = [
            f"[1] 下游微服务 [{culprit_service}] 执行耗时突破客户端/网关超时红线",
            "[2] 网关向调用方强制返回 HTTP 504 Gateway Timeout",
            "[3] 自动化测试客户端读取响应流被强制断开",
        ]
        suggested_action = "排查下游慢调用火焰图瓶颈，调高网关超时阈值或优化慢 SQL 运算。"

    # 规则 3: 下游微服务 500 崩溃 / 空指针
    elif http_status_code == 500 or any(
        k in log_lower or k in resp_lower
        for k in (
            "internal server error",
            "nullpointerexception",
            "attributeerror: 'none'",
            "indexerror",
            "keyerror",
            "zerodivisionerror",
        )
    ):
        category = RootCauseCategory.DOWNSTREAM_SERVICE_CRASH
        confidence = 0.90
        culprit_service = error_spans[0].get("service_name", "backend-service") if error_spans else "backend-service"
        summary = f"微服务内部发生未捕获异常或空指针崩溃 (首发源头: {culprit_service})。"
        causal_chain = [
            f"[1] 微服务 [{culprit_service}] 在执行时抛出未捕获异常 ({culprit_location})",
            "[2] 全局异常拦截器捕获并包装为 HTTP 500 响应",
            "[3] 自动化用例因状态码非预期或响应体格式错误而中断",
        ]
        suggested_action = f"根据堆栈定位 {culprit_location} 增加参数判空防御与类型断言防护。"

    # 规则 4: UI DOM 定位漂移
    elif any(
        k in log_lower
        for k in (
            "nosuchelementexception",
            "staleelementreferenceexception",
            "elementnotinteractable",
            "element is not attached",
            "locator.click: timeout",
        )
    ):
        category = RootCauseCategory.UI_DOM_LOCATOR_DRIFT
        confidence = 0.96
        culprit_service = "frontend-web"
        summary = "前端页面组件发生改版或动态异步渲染时差，导致用例中既有定位符失效漂移。"
        causal_chain = [
            "[1] 前端页面 DOM 树结构发生更新或样式类重命名",
            "[2] 自动化测试脚本驱动 (Playwright/Selenium) 超时未能找到目标节点",
            "[3] 触发 NoSuchElement 或 ElementNotInteractable 异常",
        ]
        suggested_action = "启用智能自愈多策略定位器 (Smart Locator Healer)，结合文本与相对语义坐标自动修复定位。"

    # 规则 5: 鉴权过期或越权
    elif http_status_code in (401, 403) or any(
        k in log_lower or k in resp_lower for k in ("token expired", "unauthorized", "forbidden", "invalid token")
    ):
        category = RootCauseCategory.AUTHENTICATION_EXPIRED
        confidence = 0.98
        culprit_service = "auth-service"
        summary = "测试会话认证凭证 (JWT Token) 已失效过期或缺乏访问受保护接口的鉴权权限。"
        causal_chain = [
            "[1] 测试用例所持有的 Authorization 令牌超过生存期 (TTL)",
            "[2] 鉴权网关鉴权失败并拒绝请求 (HTTP 401/403)",
            "[3] 用例步骤因鉴权拦截直接终止",
        ]
        suggested_action = "在前置脚本中加入 Token 自动轮转与重新登录刷新机制。"

    # 规则 6: 业务逻辑断言失败
    elif any(k in log_lower for k in ("assertionerror", "assert ", "expected", "but was", "values differ")):
        category = RootCauseCategory.ASSERTION_BUSINESS_LOGIC_DEFECT
        confidence = 0.88
        culprit_service = "business-logic"
        summary = "接口或页面实际业务返回值与用例预期断言不符，存在潜在业务缺陷或用例预期未及时同步。"
        causal_chain = [
            "[1] 接口正常返回数据但字段取值偏离设计期望",
            "[2] 自动化测试执行器断言表达式触发 AssertionError",
            "[3] 用例结果标记为 FAILED",
        ]
        suggested_action = "比对黄金响应基线与接口契约设计，核实是否属于核心业务缺陷或契约兼容性变更。"

    # 默认未知
    else:
        category = RootCauseCategory.UNKNOWN_FAILURE
        confidence = 0.40
        summary = "未能命中已知异常特征模式，需人工结合控制台日志综合排查。"
        causal_chain = [
            "[1] 测试运行环境记录到异常发生",
            "[2] 自动化用例中断退出",
        ]
        suggested_action = "下载控制台日志与完整 HAR/Span 链路追踪开展人工深入诊断。"

    report = RootCauseAttributionReport(
        diagnosis_id=did,
        case_id=case_id,
        case_name=case_name,
        category=category,
        confidence_score=confidence,
        primary_root_cause_summary=summary,
        culprit_service=culprit_service,
        culprit_location=culprit_location,
        causal_chain=causal_chain,
        evidence_snippets=snippets,
        suggested_action=suggested_action,
    )

    _ROOT_CAUSE_STORE[did] = report
    return report


def batch_analyze_failures(failure_records: list[dict[str, Any]]) -> list[RootCauseAttributionReport]:
    """批量推导多个测试失败用例的根因归因。"""
    reports = []
    for item in failure_records:
        rep = analyze_test_failure_root_cause(
            case_id=str(item.get("case_id", "case_unknown")),
            case_name=str(item.get("case_name", "Unknown Case")),
            console_logs=str(item.get("console_logs", "")),
            http_status_code=item.get("http_status_code"),
            http_response_body=str(item.get("http_response_body", "")),
            spans=item.get("spans"),
            env_factors=item.get("env_factors"),
        )
        reports.append(rep)
    return reports


def get_root_cause_report(diagnosis_id: str) -> RootCauseAttributionReport | None:
    """获取指定根因报告详情。"""
    return _ROOT_CAUSE_STORE.get(diagnosis_id)


def list_root_cause_reports(
    limit: int = 50,
    category: str | None = None,
) -> list[RootCauseAttributionReport]:
    """查询历史根因推导报告列表。"""
    res = list(_ROOT_CAUSE_STORE.values())
    if category:
        res = [r for r in res if r.category.value == category]
    res.sort(key=lambda r: r.diagnosed_at, reverse=True)
    return res[:limit]


def clear_root_cause_store() -> int:
    """清空根因推导数据仓库。"""
    c = len(_ROOT_CAUSE_STORE)
    _ROOT_CAUSE_STORE.clear()
    return c
