"""跨端统一语义动作模型与映射器服务 (T1.1)

解决自动化测试脚本在 Web / iOS / Android 异构环境下的割裂与重复开发难题:
1. 统一跨端语义动作抽象 (Unified Semantic Action: TAP, FILL_TEXT, SCROLL, ASSERT, WAIT);
2. 跨平台动作映射转换引擎 (Web Playwright <-> iOS WDA <-> Android UiAutomator2);
3. 定位器跨平台语法转换与置信度打分;
4. 动作序列批量智能转译与元数据对齐。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class PlatformType(str, enum.Enum):
    WEB = "web"
    IOS = "ios"
    ANDROID = "android"


class SemanticActionType(str, enum.Enum):
    TAP = "TAP"  # 点击/轻触
    DOUBLE_TAP = "DOUBLE_TAP"  # 双击
    LONG_PRESS = "LONG_PRESS"  # 长按
    FILL_TEXT = "FILL_TEXT"  # 文本输入
    CLEAR_TEXT = "CLEAR_TEXT"  # 清空输入
    SCROLL = "SCROLL"  # 滚动/滑动
    SWIPE = "SWIPE"  # 快速轻扫
    ASSERT_TEXT = "ASSERT_TEXT"  # 文本断言
    ASSERT_VISIBLE = "ASSERT_VISIBLE"  # 元素可见性断言
    WAIT_DELAY = "WAIT_DELAY"  # 等待延时
    KEY_PRESS = "KEY_PRESS"  # 按键 (Enter / Back / Home)
    SCREENSHOT = "SCREENSHOT"  # 页面截图存证


@dataclass
class SemanticLocator:
    locator_type: str  # id | css | xpath | text | accessibility_id | resource_id | predicate
    locator_value: str
    semantic_role: Optional[str] = None  # button | input | label | tab | link
    element_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticActionStep:
    step_id: str
    action_type: SemanticActionType
    source_platform: PlatformType
    target_platform: PlatformType
    source_locator: Optional[SemanticLocator]
    target_locator: Optional[SemanticLocator]
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # 映射置信度 (0.0 ~ 1.0)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action_type"] = self.action_type.value
        d["source_platform"] = self.source_platform.value
        d["target_platform"] = self.target_platform.value
        return d


@dataclass
class ActionMappingResult:
    mapping_id: str
    source_platform: PlatformType
    target_platform: PlatformType
    total_steps: int
    mapped_steps_count: int
    average_confidence: float
    mapped_steps: List[SemanticActionStep]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "source_platform": self.source_platform.value,
            "target_platform": self.target_platform.value,
            "total_steps": self.total_steps,
            "mapped_steps_count": self.mapped_steps_count,
            "average_confidence": round(self.average_confidence, 4),
            "mapped_steps": [s.to_dict() for s in self.mapped_steps],
            "created_at": self.created_at,
        }


def convert_locator_for_platform(
    source_locator: SemanticLocator,
    source_platform: PlatformType,
    target_platform: PlatformType,
) -> Tuple[SemanticLocator, float]:
    """将源平台定位器语法映射为目标平台最优定位器

    Returns:
        (SemanticLocator, confidence)
    """
    if source_platform == target_platform:
        return source_locator, 1.0

    stype = source_locator.locator_type.lower()
    sval = source_locator.locator_value
    text = source_locator.element_text or ""

    # 1. 优先使用元素文案直接对齐 (跨端最稳定)
    if text:
        if target_platform == PlatformType.ANDROID:
            return SemanticLocator("text", text, semantic_role=source_locator.semantic_role, element_text=text), 0.95
        elif target_platform == PlatformType.IOS:
            return SemanticLocator(
                "accessibility_id", text, semantic_role=source_locator.semantic_role, element_text=text
            ), 0.92
        elif target_platform == PlatformType.WEB:
            return SemanticLocator(
                "text", f"text='{text}'", semantic_role=source_locator.semantic_role, element_text=text
            ), 0.95

    # 2. Web ➔ 移动端 (iOS / Android)
    if source_platform == PlatformType.WEB:
        if stype == "id" or sval.startswith("#"):
            clean_id = sval.lstrip("#")
            if target_platform == PlatformType.ANDROID:
                return SemanticLocator("resource_id", f"{clean_id}", semantic_role=source_locator.semantic_role), 0.88
            elif target_platform == PlatformType.IOS:
                return SemanticLocator("accessibility_id", clean_id, semantic_role=source_locator.semantic_role), 0.85
        elif stype == "xpath":
            return SemanticLocator("xpath", sval, semantic_role=source_locator.semantic_role), 0.75

    # 3. iOS ➔ Android
    if source_platform == PlatformType.IOS and target_platform == PlatformType.ANDROID:
        if stype in ("accessibility_id", "name", "id"):
            return SemanticLocator("resource_id", sval, semantic_role=source_locator.semantic_role), 0.90
        elif stype == "predicate":
            return SemanticLocator("text", sval, semantic_role=source_locator.semantic_role), 0.70

    # 4. Android ➔ iOS
    if source_platform == PlatformType.ANDROID and target_platform == PlatformType.IOS:
        if stype in ("resource_id", "id"):
            clean_id = sval.split("/")[-1] if "/" in sval else sval
            return SemanticLocator("accessibility_id", clean_id, semantic_role=source_locator.semantic_role), 0.90
        elif stype == "text":
            return SemanticLocator("accessibility_id", sval, semantic_role=source_locator.semantic_role), 0.88

    # 5. 兜底通用映射
    return SemanticLocator("xpath", sval, semantic_role=source_locator.semantic_role), 0.65


def map_action_step(
    raw_step: Dict[str, Any],
    source_platform: PlatformType,
    target_platform: PlatformType,
) -> SemanticActionStep:
    """转译单条操作动作"""
    step_id = raw_step.get("step_id") or f"step_{uuid.uuid4().hex[:8]}"
    raw_action = str(raw_step.get("action_type", "TAP")).upper()

    try:
        action_type = SemanticActionType(raw_action)
    except ValueError:
        action_type = SemanticActionType.TAP

    # 提取源定位器
    source_loc_data = raw_step.get("locator") or raw_step.get("source_locator")
    source_locator: Optional[SemanticLocator] = None
    target_locator: Optional[SemanticLocator] = None
    confidence = 1.0

    if source_loc_data:
        if isinstance(source_loc_data, dict):
            source_locator = SemanticLocator(
                locator_type=str(source_loc_data.get("type", "id")),
                locator_value=str(source_loc_data.get("value", "")),
                semantic_role=source_loc_data.get("role"),
                element_text=source_loc_data.get("text") or raw_step.get("text"),
            )
        elif isinstance(source_loc_data, str):
            source_locator = SemanticLocator(
                locator_type="text" if not source_loc_data.startswith(("/", "#", ".")) else "css",
                locator_value=source_loc_data,
                element_text=raw_step.get("text"),
            )

    if source_locator:
        target_locator, confidence = convert_locator_for_platform(source_locator, source_platform, target_platform)

    # 适配参数
    params = dict(raw_step.get("parameters") or {})
    if "input_text" in raw_step:
        params["text"] = raw_step["input_text"]
    if "expected_text" in raw_step:
        params["expected_text"] = raw_step["expected_text"]

    notes = f"从 [{source_platform.value}] 自动映射转译至 [{target_platform.value}]"

    return SemanticActionStep(
        step_id=step_id,
        action_type=action_type,
        source_platform=source_platform,
        target_platform=target_platform,
        source_locator=source_locator,
        target_locator=target_locator,
        parameters=params,
        confidence=confidence,
        notes=notes,
    )


def map_cross_platform_actions(
    raw_steps: List[Dict[str, Any]],
    source_platform: PlatformType,
    target_platform: PlatformType,
) -> ActionMappingResult:
    """批量映射转译测试用例动作序列"""
    mapping_id = f"map_{uuid.uuid4().hex[:12]}"
    mapped_steps: List[SemanticActionStep] = []

    for raw_step in raw_steps:
        step = map_action_step(raw_step, source_platform, target_platform)
        mapped_steps.append(step)

    avg_conf = sum(s.confidence for s in mapped_steps) / len(mapped_steps) if mapped_steps else 1.0

    return ActionMappingResult(
        mapping_id=mapping_id,
        source_platform=source_platform,
        target_platform=target_platform,
        total_steps=len(raw_steps),
        mapped_steps_count=len(mapped_steps),
        average_confidence=avg_conf,
        mapped_steps=mapped_steps,
    )
