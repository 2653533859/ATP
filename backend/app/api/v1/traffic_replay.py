"""影子流量无副作用沙箱隔离回放 REST API (T2.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.shadow_traffic_replay_engine import (
    MockRuleConfig,
    ReplayJobConfig,
    WriteGuardMode,
    clear_replay_sessions,
    execute_shadow_replay,
    get_default_external_mock_rules,
    get_replay_session,
    list_replay_sessions,
)
from app.services.traffic_capture_gateway import list_captured_traffic

router = APIRouter(prefix="/traffic/replay", tags=["影子流量隔离回放引擎 (T2.1)"])


class MockRuleIn(BaseModel):
    rule_id: str = Field(..., description="规则唯一标识")
    name: str = Field(..., description="规则名称")
    pattern: str = Field(..., description="URL 或 Host 正则匹配表达式")
    mock_status_code: int = Field(default=200, description="模拟返回状态码")
    mock_response_body: str = Field(default='{"mock": true}', description="模拟返回体")
    enabled: bool = Field(default=True, description="是否启用")


class RunShadowReplayIn(BaseModel):
    target_base_url: str = Field(default="http://127.0.0.1:8000", description="回放目标服务 Base URL")
    write_guard_mode: str = Field(
        default="BLOCK_WRITES",
        description="写操作防护模式: BLOCK_WRITES (默认拦截写) | SHADOW_HEADER_ONLY | ALLOW_ALL | DRY_RUN",
    )
    rate_limit_qps: float = Field(default=20.0, ge=0.1, le=500.0, description="回放流速 QPS 上限")
    timeout_sec: float = Field(default=5.0, ge=0.5, le=60.0, description="单次请求超时上限 (秒)")
    inject_headers: dict[str, str] = Field(default_factory=dict, description="额外自定义注入的出站请求头")
    external_mock_rules: list[MockRuleIn] | None = Field(default=None, description="自定义外部不可控依赖 Mock 规则")
    stop_on_error: bool = Field(default=False, description="遇到错误是否提前终止")
    traffic_records: list[dict[str, Any]] | None = Field(
        default=None, description="待回放的流量记录列表。若留空则自动从系统已捕获的流量库中提取"
    )
    limit_captured: int = Field(default=50, ge=1, le=500, description="从系统捕获库提取的最大流量条数")


@router.post("/run")
async def run_shadow_replay_endpoint(
    body: RunShadowReplayIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """触发影子流量无副作用沙箱回放 (需工程师权限)。"""
    _ = _user
    try:
        guard_mode = WriteGuardMode(body.write_guard_mode.upper())
    except ValueError:
        guard_mode = WriteGuardMode.BLOCK_WRITES

    # 构建 mock 规则
    mock_rules: list[MockRuleConfig] = []
    if body.external_mock_rules:
        for r in body.external_mock_rules:
            mock_rules.append(
                MockRuleConfig(
                    rule_id=r.rule_id,
                    name=r.name,
                    pattern=r.pattern,
                    mock_status_code=r.mock_status_code,
                    mock_response_body=r.mock_response_body,
                    enabled=r.enabled,
                )
            )
    else:
        mock_rules = get_default_external_mock_rules()

    config = ReplayJobConfig(
        target_base_url=body.target_base_url,
        write_guard_mode=guard_mode,
        rate_limit_qps=body.rate_limit_qps,
        timeout_sec=body.timeout_sec,
        inject_headers=body.inject_headers,
        external_mock_rules=mock_rules,
        stop_on_error=body.stop_on_error,
    )

    records = body.traffic_records
    if records is None:
        captured = list_captured_traffic(limit=body.limit_captured)
        records = [c.to_dict() for c in captured]

    report = execute_shadow_replay(records=records, config=config)

    return {
        "message": f"影子流量回放完成：总计 {report.total_items} 条，成功 {report.success_count}，写安全拦截 {report.blocked_write_count}，外部Mock {report.mocked_external_count}",
        "report": report.to_dict(),
    }


@router.get("/sessions")
async def list_replay_sessions_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史影子回放批次报告列表。"""
    _ = _user
    sessions = list_replay_sessions()
    return {"total": len(sessions), "sessions": [s.to_dict() for s in sessions]}


@router.get("/sessions/{session_id}")
async def get_replay_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定影子回放批次的详细流水报告。"""
    _ = _user
    session = get_replay_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"回放会话不存在: {session_id}")
    return session.to_dict()


@router.get("/mock-rules/defaults")
async def get_default_mock_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取系统出厂默认的外部不可控依赖 (支付/短信/邮件) Mock 规则列表。"""
    _ = _user
    rules = get_default_external_mock_rules()
    return {"rules": [r.to_dict() for r in rules]}


@router.delete("/sessions")
async def clear_replay_sessions_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空影子回放历史会话记录 (需工程师权限)。"""
    _ = _user
    count = clear_replay_sessions()
    return {"message": f"已清空 {count} 条回放记录", "deleted_count": count}
