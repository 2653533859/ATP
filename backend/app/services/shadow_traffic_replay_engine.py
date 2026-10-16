"""影子流量无副作用沙箱隔离回放与外部依赖 Mock 代理服务 (T2.1)。

负责将生产捕获或脱敏后的流量在隔离环境进行无害化影子回放：
1. 影子流量标记注入 (X-Shadow-Traffic / Session-Id / Trace-Id)；
2. 写操作无副作用拦截 (BLOCK_WRITES / DRY_RUN)；
3. 外部第三方下游不可控依赖自动拦截与 Mock 代理；
4. 并发流速控制与回放执行状态流水度量。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import re
import time
from typing import Any, Callable
import uuid

import httpx

logger = logging.getLogger(__name__)


class WriteGuardMode(str, Enum):
    BLOCK_WRITES = "BLOCK_WRITES"  # 严格拦截所有写操作 (POST/PUT/DELETE/PATCH)，返回虚拟安全响应
    SHADOW_HEADER_ONLY = "SHADOW_HEADER_ONLY"  # 注入 X-Shadow-Traffic 头部并正常发出请求 (需被测端支持影子库)
    ALLOW_ALL = "ALLOW_ALL"  # 允许所有请求正常发出 (用于独立隔离测试环境)
    DRY_RUN = "DRY_RUN"  # 纯演练模式，不发生任何真实网络 Socket 交互


@dataclass
class MockRuleConfig:
    rule_id: str
    name: str
    pattern: str  # host 或 url 正则匹配 (如 r".*alipay\.com.*", r".*sms.*")
    mock_status_code: int = 200
    mock_response_body: str = '{"code": 0, "mock": true, "message": "Shadow Mock Intercepted"}'
    mock_headers: dict[str, str] = field(default_factory=lambda: {"content-type": "application/json"})
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "pattern": self.pattern,
            "mock_status_code": self.mock_status_code,
            "mock_response_body": self.mock_response_body,
            "mock_headers": self.mock_headers,
            "enabled": self.enabled,
        }


def get_default_external_mock_rules() -> list[MockRuleConfig]:
    """内置常见的外部支付、短信、邮件第三方不可控网关 Mock 规则。"""
    return [
        MockRuleConfig(
            rule_id="mock_payment",
            name="第三方支付网关拦截 (微信/支付宝)",
            pattern=r"(?i).*(alipay|wxpay|pay\.wechat|stripe|paypal).*",
            mock_status_code=200,
            mock_response_body='{"code": 0, "status": "SUCCESS", "trade_state": "SUCCESS", "mock": true}',
        ),
        MockRuleConfig(
            rule_id="mock_sms_push",
            name="短信与消息推送服务拦截",
            pattern=r"(?i).*(sms|push|message|notification|getui|jpush).*",
            mock_status_code=200,
            mock_response_body='{"code": 0, "message": "SMS Mock Sent", "mock": true}',
        ),
        MockRuleConfig(
            rule_id="mock_mail",
            name="外发邮件服务拦截",
            pattern=r"(?i).*(smtp|sendmail|mail|email).*",
            mock_status_code=200,
            mock_response_body='{"code": 0, "message": "Email Mock Queued", "mock": true}',
        ),
    ]


@dataclass
class ReplayJobConfig:
    target_base_url: str = "http://127.0.0.1:8000"
    write_guard_mode: WriteGuardMode = WriteGuardMode.BLOCK_WRITES
    rate_limit_qps: float = 20.0
    timeout_sec: float = 5.0
    inject_headers: dict[str, str] = field(default_factory=dict)
    external_mock_rules: list[MockRuleConfig] = field(default_factory=get_default_external_mock_rules)
    stop_on_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_base_url": self.target_base_url,
            "write_guard_mode": self.write_guard_mode.value,
            "rate_limit_qps": self.rate_limit_qps,
            "timeout_sec": self.timeout_sec,
            "inject_headers": self.inject_headers,
            "external_mock_rules": [r.to_dict() for r in self.external_mock_rules],
            "stop_on_error": self.stop_on_error,
        }


@dataclass
class ReplayItemResult:
    item_id: str
    traffic_id: str
    method: str
    path_or_endpoint: str
    executed_url: str
    original_status_code: int
    replayed_status_code: int
    duration_ms: float
    was_mocked: bool
    mock_reason: str | None
    was_write_blocked: bool
    replayed_response_body: str
    success: bool
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "traffic_id": self.traffic_id,
            "method": self.method,
            "path_or_endpoint": self.path_or_endpoint,
            "executed_url": self.executed_url,
            "original_status_code": self.original_status_code,
            "replayed_status_code": self.replayed_status_code,
            "duration_ms": round(self.duration_ms, 2),
            "was_mocked": self.was_mocked,
            "mock_reason": self.mock_reason,
            "was_write_blocked": self.was_write_blocked,
            "replayed_response_body": self.replayed_response_body[:2048],
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass
class ReplaySessionReport:
    session_id: str
    target_base_url: str
    write_guard_mode: str
    total_items: int
    success_count: int
    failure_count: int
    blocked_write_count: int
    mocked_external_count: int
    avg_duration_ms: float
    results: list[ReplayItemResult]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_base_url": self.target_base_url,
            "write_guard_mode": self.write_guard_mode,
            "total_items": self.total_items,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "blocked_write_count": self.blocked_write_count,
            "mocked_external_count": self.mocked_external_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "results": [r.to_dict() for r in self.results],
            "created_at": self.created_at.isoformat(),
        }


# 全局内存报告仓库
_REPLAY_SESSIONS: dict[str, ReplaySessionReport] = {}


def _match_mock_rule(url_or_path: str, rules: list[MockRuleConfig]) -> MockRuleConfig | None:
    """检查请求是否命中外部第三方不可控下游 Mock 规则。"""
    for rule in rules:
        if not rule.enabled:
            continue
        try:
            if re.search(rule.pattern, url_or_path):
                return rule
        except re.error:
            if rule.pattern.lower() in url_or_path.lower():
                return rule
    return None


def execute_shadow_replay(
    records: list[dict[str, Any]],
    config: ReplayJobConfig,
    _custom_http_requester: Callable[..., Any] | None = None,
) -> ReplaySessionReport:
    """执行影子流量无副作用沙箱回放。"""
    session_id = f"rpl_{uuid.uuid4().hex[:12]}"
    target_base = config.target_base_url.rstrip("/")

    results: list[ReplayItemResult] = []
    success_count = 0
    failure_count = 0
    blocked_write_count = 0
    mocked_external_count = 0
    total_duration = 0.0

    # QPS 节流控制间隔
    min_interval_sec = 1.0 / max(0.1, config.rate_limit_qps)
    last_exec_time = 0.0

    for item in records:
        traffic_id = str(item.get("traffic_id", f"trf_{uuid.uuid4().hex[:8]}"))
        method = str(item.get("method", "GET")).upper()
        # 兼容 gRPC 方法字符串格式 "POST /service/method"
        http_method = method.split()[0] if " " in method else method
        raw_path = str(item.get("path_or_endpoint", "/")).lstrip("/")
        full_url = f"{target_base}/{raw_path}"
        orig_status = int(item.get("response_status_code", 200))

        headers = dict(item.get("headers", {}))
        # 注入影子标识与链路追踪头
        headers["X-Shadow-Traffic"] = "true"
        headers["X-ATP-Replay-Session-Id"] = session_id
        headers["X-ATP-Replay-Time"] = datetime.now(timezone.utc).isoformat()
        headers.update(config.inject_headers)

        req_body = item.get("request_body", "")
        params = item.get("query_params", {})

        # 1. 外部依赖 Mock 检查
        matched_mock = _match_mock_rule(full_url, config.external_mock_rules)
        if matched_mock:
            mocked_external_count += 1
            success_count += 1
            res_item = ReplayItemResult(
                item_id=f"rit_{uuid.uuid4().hex[:8]}",
                traffic_id=traffic_id,
                method=method,
                path_or_endpoint=f"/{raw_path}",
                executed_url=full_url,
                original_status_code=orig_status,
                replayed_status_code=matched_mock.mock_status_code,
                duration_ms=2.0,
                was_mocked=True,
                mock_reason=f"命中第三方外部依赖 Mock 规则: {matched_mock.name}",
                was_write_blocked=False,
                replayed_response_body=matched_mock.mock_response_body,
                success=True,
                error_message=None,
            )
            results.append(res_item)
            continue

        # 2. 写操作无副作用安全拦截 (BLOCK_WRITES)
        is_write_method = http_method in ("POST", "PUT", "DELETE", "PATCH")
        if config.write_guard_mode == WriteGuardMode.BLOCK_WRITES and is_write_method:
            blocked_write_count += 1
            success_count += 1
            safe_resp = json.dumps(
                {
                    "code": 0,
                    "shadow_blocked": True,
                    "message": f"ATP 安全防护：写操作 [{http_method}] 已被影子回放引擎安全拦截，未产生线上副作用",
                },
                ensure_ascii=False,
            )
            res_item = ReplayItemResult(
                item_id=f"rit_{uuid.uuid4().hex[:8]}",
                traffic_id=traffic_id,
                method=method,
                path_or_endpoint=f"/{raw_path}",
                executed_url=full_url,
                original_status_code=orig_status,
                replayed_status_code=200,
                duration_ms=1.5,
                was_mocked=False,
                mock_reason=None,
                was_write_blocked=True,
                replayed_response_body=safe_resp,
                success=True,
                error_message=None,
            )
            results.append(res_item)
            continue

        # 3. 纯演练模式 (DRY_RUN)
        if config.write_guard_mode == WriteGuardMode.DRY_RUN:
            success_count += 1
            res_item = ReplayItemResult(
                item_id=f"rit_{uuid.uuid4().hex[:8]}",
                traffic_id=traffic_id,
                method=method,
                path_or_endpoint=f"/{raw_path}",
                executed_url=full_url,
                original_status_code=orig_status,
                replayed_status_code=orig_status,
                duration_ms=1.0,
                was_mocked=False,
                mock_reason=None,
                was_write_blocked=False,
                replayed_response_body='{"dry_run": true}',
                success=True,
                error_message=None,
            )
            results.append(res_item)
            continue

        # 4. QPS 速率控制
        now = time.time()
        elapsed_since_last = now - last_exec_time
        if elapsed_since_last < min_interval_sec:
            time.sleep(min_interval_sec - elapsed_since_last)
        last_exec_time = time.time()

        # 5. 真实/自定义客户端发出请求
        start_t = time.perf_counter()
        replayed_code = 500
        replayed_body = ""
        is_succ = False
        err_msg = None

        try:
            if _custom_http_requester:
                # 供单元测试注入模拟请求
                resp = _custom_http_requester(http_method, full_url, headers=headers, params=params, data=req_body)
                replayed_code = getattr(resp, "status_code", 200)
                replayed_body = getattr(resp, "text", str(resp))
                is_succ = True
            else:
                with httpx.Client(timeout=config.timeout_sec) as client:
                    resp = client.request(
                        method=http_method,
                        url=full_url,
                        headers=headers,
                        params=params,
                        content=req_body.encode("utf-8") if isinstance(req_body, str) else None,
                    )
                    replayed_code = resp.status_code
                    replayed_body = resp.text
                    is_succ = replayed_code < 500
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"
            replayed_code = 504
            is_succ = False

        duration = round((time.perf_counter() - start_t) * 1000, 2)
        total_duration += duration

        if is_succ:
            success_count += 1
        else:
            failure_count += 1

        res_item = ReplayItemResult(
            item_id=f"rit_{uuid.uuid4().hex[:8]}",
            traffic_id=traffic_id,
            method=method,
            path_or_endpoint=f"/{raw_path}",
            executed_url=full_url,
            original_status_code=orig_status,
            replayed_status_code=replayed_code,
            duration_ms=duration,
            was_mocked=False,
            mock_reason=None,
            was_write_blocked=False,
            replayed_response_body=replayed_body,
            success=is_succ,
            error_message=err_msg,
        )
        results.append(res_item)

        if not is_succ and config.stop_on_error:
            logger.warning("回放遇错且配置了 stop_on_error，提前终止后续请求")
            break

    avg_dur = round(total_duration / max(1, len(results)), 2)
    report = ReplaySessionReport(
        session_id=session_id,
        target_base_url=config.target_base_url,
        write_guard_mode=config.write_guard_mode.value,
        total_items=len(results),
        success_count=success_count,
        failure_count=failure_count,
        blocked_write_count=blocked_write_count,
        mocked_external_count=mocked_external_count,
        avg_duration_ms=avg_dur,
        results=results,
    )

    _REPLAY_SESSIONS[session_id] = report
    logger.info(
        "影子回放批次 [%s] 完成: 总计 %d 条，成功 %d，写拦截 %d，外部Mock %d",
        session_id,
        len(results),
        success_count,
        blocked_write_count,
        mocked_external_count,
    )
    return report


def get_replay_session(session_id: str) -> ReplaySessionReport | None:
    """根据 ID 获取指定影子回放批次报告详情。"""
    return _REPLAY_SESSIONS.get(session_id)


def list_replay_sessions() -> list[ReplaySessionReport]:
    """获取历史影子回放批次报告列表。"""
    sessions = list(_REPLAY_SESSIONS.values())
    sessions.sort(key=lambda s: s.created_at, reverse=True)
    return sessions


def clear_replay_sessions() -> int:
    """清空影子回放历史会话记录。"""
    count = len(_REPLAY_SESSIONS)
    _REPLAY_SESSIONS.clear()
    return count
