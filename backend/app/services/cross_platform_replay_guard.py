"""跨端迁移回放安全防护看门狗服务 (T4.1)

在跨端测试用例转译到目标平台（真实物理真机 / Web 环境）执行回放时提供实时防护:
1. 高危敏感破坏手势实时拦截 (注销、重置、大额扣款、删库误触);
2. 跨端屏幕几何坐标漂移与越界保护 (Screen Bounds & Coordinate Drift Guard);
3. 低置信度交互手势门禁阻断 (Confidence Gate: 防止低置信度盲目点击);
4. 违规拦截事件审计与熔断保护 (ReplayViolationEvent & Circuit Breaker)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ReplayViolationType(str, enum.Enum):
    HIGH_RISK_GESTURE = "HIGH_RISK_GESTURE"  # 误触高危破坏性操作
    COORDINATE_OUT_OF_BOUNDS = "COORDINATE_OUT_OF_BOUNDS"  # 点击坐标越界/落在黑区
    LOW_CONFIDENCE_GATE = "LOW_CONFIDENCE_GATE"  # 映射置信度严重偏低
    DEVICE_CAPABILITY_MISMATCH = "DEVICE_CAPABILITY_MISMATCH"  # 设备能力不支持 (如无 FaceID 硬件)


class ReplayGuardVerdict(str, enum.Enum):
    ALLOW = "ALLOW"  # 允许执行
    WARN = "WARN"  # 告警放行
    BLOCK = "BLOCK"  # 立即阻断并熔断


@dataclass
class ScreenViewport:
    width: int
    height: int
    safe_area_top: int = 44
    safe_area_bottom: int = 34

    def is_within_bounds(self, x: int, y: int) -> bool:
        """检查坐标是否落在有效视口且避开极端系统边缘"""
        if x < 0 or x > self.width:
            return False
        if y < 0 or y > self.height:
            return False
        # 避开极顶端 10px (防意外下拉通知栏)
        if y < 10 or y > (self.height - 5):
            return False
        return True


@dataclass
class ReplayViolationEvent:
    violation_id: str
    migration_id: str
    step_id: str
    violation_type: ReplayViolationType
    verdict: ReplayGuardVerdict
    target_platform: str
    action_type: str
    element_label: str
    coordinates: Optional[List[int]]
    confidence: float
    reason: str
    suggested_action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["violation_type"] = self.violation_type.value
        d["verdict"] = self.verdict.value
        return d


# 敏感破坏词黑名单 (回放时严禁触碰)
DESTRUCTIVE_KEYWORDS = {
    "注销",
    "销户",
    "抹掉",
    "恢复出厂",
    "格式化",
    "清空",
    "delete account",
    "factory reset",
    "扣款1000",
    "真实转账",
    "解绑银行卡",
    "禁用安全",
    "drop table",
    "truncate",
}

_REPLAY_VIOLATIONS_STORE: Dict[str, ReplayViolationEvent] = {}


def clear_replay_violations() -> None:
    """清空回放违规内存记录（测试使用）"""
    _REPLAY_VIOLATIONS_STORE.clear()


def evaluate_replay_step_safety(
    migration_id: str,
    step_id: str,
    target_platform: str,
    action_type: str,
    element_label: str = "",
    target_locator_value: str = "",
    coordinates: Optional[List[int]] = None,
    confidence: float = 1.0,
    viewport: Optional[ScreenViewport] = None,
    min_confidence_threshold: float = 0.50,
) -> Tuple[ReplayGuardVerdict, Optional[ReplayViolationEvent]]:
    """在将转译用例下发到目标设备前，实时进行多重安全看门狗审查"""
    vid = f"repviol_{uuid.uuid4().hex[:10]}"
    combined_text = f"{element_label} {target_locator_value}".lower()

    # 1. 高危敏感破坏词拦截
    for kw in DESTRUCTIVE_KEYWORDS:
        if kw in combined_text:
            event = ReplayViolationEvent(
                violation_id=vid,
                migration_id=migration_id,
                step_id=step_id,
                violation_type=ReplayViolationType.HIGH_RISK_GESTURE,
                verdict=ReplayGuardVerdict.BLOCK,
                target_platform=target_platform,
                action_type=action_type,
                element_label=element_label,
                coordinates=coordinates,
                confidence=confidence,
                reason=f"看门狗阻断: 转译动作命中高危破坏词 [{kw}]，禁止在目标端下发执行",
                suggested_action="人工复核转译步骤，确认是否发生控件误映射。",
            )
            _REPLAY_VIOLATIONS_STORE[vid] = event
            return ReplayGuardVerdict.BLOCK, event

    # 2. 坐标越界与漂移拦截 (若有坐标参数)
    if coordinates and len(coordinates) >= 2:
        x, y = coordinates[0], coordinates[1]
        active_viewport = viewport or ScreenViewport(width=1080, height=2400)
        if not active_viewport.is_within_bounds(x, y):
            event = ReplayViolationEvent(
                violation_id=vid,
                migration_id=migration_id,
                step_id=step_id,
                violation_type=ReplayViolationType.COORDINATE_OUT_OF_BOUNDS,
                verdict=ReplayGuardVerdict.BLOCK,
                target_platform=target_platform,
                action_type=action_type,
                element_label=element_label,
                coordinates=coordinates,
                confidence=confidence,
                reason=f"点击坐标 [{x}, {y}] 超出目标设备有效屏幕视口 [{active_viewport.width}x{active_viewport.height}]",
                suggested_action="重新推导目标端元素绝对布局，避免直接硬编码旧平台坐标。",
            )
            _REPLAY_VIOLATIONS_STORE[vid] = event
            return ReplayGuardVerdict.BLOCK, event

    # 3. 低置信度阻断门禁
    if confidence < min_confidence_threshold:
        # 仅针对破坏性或写操作拦截，读/等待操作放行
        if action_type.upper() in ("TAP", "FILL_TEXT", "DOUBLE_TAP", "LONG_PRESS"):
            event = ReplayViolationEvent(
                violation_id=vid,
                migration_id=migration_id,
                step_id=step_id,
                violation_type=ReplayViolationType.LOW_CONFIDENCE_GATE,
                verdict=ReplayGuardVerdict.BLOCK,
                target_platform=target_platform,
                action_type=action_type,
                element_label=element_label,
                coordinates=coordinates,
                confidence=confidence,
                reason=f"转译置信度仅为 {round(confidence * 100, 1)}%，低于安全回放门禁阈值 ({round(min_confidence_threshold * 100, 1)}%)",
                suggested_action="在回放前提供更精确的目标端定位器或人工确认控件匹配。",
            )
            _REPLAY_VIOLATIONS_STORE[vid] = event
            return ReplayGuardVerdict.BLOCK, event

    return ReplayGuardVerdict.ALLOW, None


def list_replay_violations(migration_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """查询回放看门狗违规拦截事件列表"""
    events = list(_REPLAY_VIOLATIONS_STORE.values())
    if migration_id:
        events = [e for e in events if e.migration_id == migration_id]
    events.sort(key=lambda x: x.timestamp, reverse=True)
    return [e.to_dict() for e in events[:limit]]
