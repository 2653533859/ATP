"""探索过程白屏、死锁与崩溃异常侦测器服务 (T2.2)

负责在多模态自主探索过程中实时检测异常界面缺陷并触发快速熔断保护:
1. 界面白屏/黑屏检测 (Blank / White / Black Screen Detector);
2. 页面状态无响应死锁 (State Deadlock & Loop Stall);
3. 业务与系统错误弹窗拦截 (Error Dialog / Network Error);
4. 异常等级定级 (CRITICAL | HIGH | MEDIUM) 与告警事件归档。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.vlm_autonomous_explorer import (
    DetectedUIElement,
    ExplorationSession,
)


class AnomalyType(str, Enum):
    WHITE_SCREEN = "WHITE_SCREEN"
    BLACK_SCREEN = "BLACK_SCREEN"
    STATE_DEADLOCK = "STATE_DEADLOCK"
    ERROR_DIALOG = "ERROR_DIALOG"
    APP_CRASH = "APP_CRASH"


class AnomalySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


@dataclass
class ExplorationAnomalyRecord:
    anomaly_id: str
    session_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    state_id: Optional[str]
    title: str
    description: str
    suggested_action: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "session_id": self.session_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "state_id": self.state_id,
            "title": self.title,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "detected_at": self.detected_at,
        }


# 全局轻量级探索异常字典
_ANOMALY_RECORDS: Dict[str, ExplorationAnomalyRecord] = {}


def clear_anomaly_records() -> None:
    _ANOMALY_RECORDS.clear()


def list_anomaly_records(session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    records = list(_ANOMALY_RECORDS.values())
    if session_id:
        records = [r for r in records if r.session_id == session_id]
    return [r.to_dict() for r in reversed(records[-limit:])]


def inspect_screen_anomaly(
    session: ExplorationSession,
    screenshot_b64: str,
    elements: List[DetectedUIElement],
    consecutive_same_state_count: int = 0,
) -> Optional[ExplorationAnomalyRecord]:
    """对当前界面与探索状态执行综合异常巡检"""
    aid = f"anom_{uuid.uuid4().hex[:12]}"

    # 1. 界面白屏或无控件异常 (若可交互控件为 0 或截图过小)
    if len(elements) == 0 or len(screenshot_b64) < 50:
        rec = ExplorationAnomalyRecord(
            anomaly_id=aid,
            session_id=session.session_id,
            anomaly_type=AnomalyType.WHITE_SCREEN,
            severity=AnomalySeverity.CRITICAL,
            state_id=session.current_state_id,
            title="检测到界面疑似白屏或无控件响应",
            description="视觉模型在当前屏幕视口内未能感知到任何可交互控件，可能发生白屏崩溃或首屏加载卡死。",
            suggested_action="请检查前端控制台 JS 抛错与移动端 Activity/ViewController 渲染日志。",
        )
        _ANOMALY_RECORDS[aid] = rec
        return rec

    # 2. 状态死循环卡死检测 (连续多次操作未能发生任何状态迁移)
    if consecutive_same_state_count >= 4:
        rec = ExplorationAnomalyRecord(
            anomaly_id=aid,
            session_id=session.session_id,
            anomaly_type=AnomalyType.STATE_DEADLOCK,
            severity=AnomalySeverity.HIGH,
            state_id=session.current_state_id,
            title="检测到界面交互死循环/无响应卡死",
            description=f"在状态 [{session.current_state_id}] 下已连续执行 {consecutive_same_state_count} 次交互手势，界面未发生任何状态迁移。",
            suggested_action="建议对该控件触发系统级返回键或跳过循环节点。",
        )
        _ANOMALY_RECORDS[aid] = rec
        return rec

    # 3. 错误弹窗智能拦截 (检测到包含严重报错关键字的按钮或文本)
    for el in elements:
        lbl = el.label.lower()
        if any(k in lbl for k in ("网络错误", "系统异常", "无法连接", "error 500", "崩溃", "fail", "timeout")):
            rec = ExplorationAnomalyRecord(
                anomaly_id=aid,
                session_id=session.session_id,
                anomaly_type=AnomalyType.ERROR_DIALOG,
                severity=AnomalySeverity.HIGH,
                state_id=session.current_state_id,
                title=f"捕获到界面业务错误弹窗: [{el.label}]",
                description=f"在界面中识别到异常文本控件: {el.label}，可能因下游后端服务报错触发弹窗。",
                suggested_action="点击确认或取消关闭弹窗，并排查后端微服务调用链错误日志。",
            )
            _ANOMALY_RECORDS[aid] = rec
            return rec

    return None
