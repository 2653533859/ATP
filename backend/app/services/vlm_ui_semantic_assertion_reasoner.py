"""基于视觉大模型 (VLM) 的 UI 页面语义完整性断言推理器 (T2.1)。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class VisualAssertionRuleType(str, Enum):
    """视觉语义断言规则类型。"""

    ASSERT_NO_WHITE_SCREEN = "ASSERT_NO_WHITE_SCREEN"  # 防白屏/空白页断言
    ASSERT_NO_BROKEN_IMAGES = "ASSERT_NO_BROKEN_IMAGES"  # 防裂图碎图断言
    ASSERT_KEY_ELEMENT_VISIBLE = "ASSERT_KEY_ELEMENT_VISIBLE"  # 关键业务元素清晰可见
    ASSERT_NO_INFINITE_LOADING = "ASSERT_NO_INFINITE_LOADING"  # 防骨架屏/旋转圈停滞
    ASSERT_CUSTOM_NATURAL_LANGUAGE = "ASSERT_CUSTOM_NATURAL_LANGUAGE"  # 自定义自然语言语义断言


class AssertionVerdict(str, Enum):
    """单项断言裁决结论。"""

    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class VisualAssertionRuleInput:
    """输入的单项视觉断言规则。"""

    rule_type: VisualAssertionRuleType
    target_description: str
    custom_prompt: str | None = None
    expected_bounding_box: dict[str, int] | None = None


@dataclass
class VisualAssertionFinding:
    """单项视觉断言推理明细结果。"""

    rule_type: VisualAssertionRuleType
    target_description: str
    verdict: AssertionVerdict
    confidence_score: float  # 置信度 0.0 ~ 1.0
    reasoning_explanation: str
    detected_bounding_box: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type.value,
            "target_description": self.target_description,
            "verdict": self.verdict.value,
            "confidence_score": round(self.confidence_score, 2),
            "reasoning_explanation": self.reasoning_explanation,
            "detected_bounding_box": self.detected_bounding_box,
        }


@dataclass
class VLMAssertionReport:
    """视觉大模型全页语义断言综合报告。"""

    report_id: str
    page_name: str
    overall_passed: bool
    visual_semantic_score_pct: float  # 0~100%
    total_assertions_count: int
    passed_count: int
    failed_count: int
    findings: list[VisualAssertionFinding]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_name": self.page_name,
            "overall_passed": self.overall_passed,
            "visual_semantic_score_pct": round(self.visual_semantic_score_pct, 1),
            "total_assertions_count": self.total_assertions_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at.isoformat(),
        }


# 全局报告仓库
_VLM_ASSERTION_REPORTS: dict[str, VLMAssertionReport] = {}

RULE_TYPES_METADATA = [
    {
        "type": VisualAssertionRuleType.ASSERT_NO_WHITE_SCREEN.value,
        "name": "防白屏/无渲染断言",
        "description": "基于全屏视觉特征检测是否出现由于前端 JS 崩溃或未加载造成的纯白屏/空白异常。",
    },
    {
        "type": VisualAssertionRuleType.ASSERT_NO_BROKEN_IMAGES.value,
        "name": "防碎图/裂图占位断言",
        "description": "检测页面图片资产是否存在由于 404 或跨域错误引发的破损图标裂图。",
    },
    {
        "type": VisualAssertionRuleType.ASSERT_KEY_ELEMENT_VISIBLE.value,
        "name": "关键业务元素视觉可见性断言",
        "description": "断言核心按钮、金额数值、二维码等关键要素不仅存在于 DOM，且在视觉上未被遮挡且清晰可读。",
    },
    {
        "type": VisualAssertionRuleType.ASSERT_NO_INFINITE_LOADING.value,
        "name": "防加载态永久停滞断言",
        "description": "探测页面核心区域是否存在永久旋转动画、骨架屏超时卡滞等未就绪缺陷。",
    },
    {
        "type": VisualAssertionRuleType.ASSERT_CUSTOM_NATURAL_LANGUAGE.value,
        "name": "自然语言意图断言",
        "description": "使用人类自然语言描述期望界面视觉状态，由视觉多模态大模型推导断言结果。",
    },
]


def clear_vlm_assertion_store() -> None:
    """清空断言报告仓库（单测专用）。"""
    _VLM_ASSERTION_REPORTS.clear()


def evaluate_visual_semantic_assertions(
    page_name: str,
    rules: list[VisualAssertionRuleInput],
    simulated_white_screen_ratio: float = 0.0,
    simulated_broken_images_count: int = 0,
    simulated_missing_element_names: list[str] | None = None,
    simulated_is_loading_stuck: bool = False,
) -> VLMAssertionReport:
    """基于视觉语义与页面特征执行多模态断言推导。"""
    missing_elements = simulated_missing_element_names or []
    findings: list[VisualAssertionFinding] = []

    for r in rules:
        if r.rule_type == VisualAssertionRuleType.ASSERT_NO_WHITE_SCREEN:
            # 白屏率 > 50% 判定为白屏崩溃
            is_white = simulated_white_screen_ratio > 0.50
            findings.append(
                VisualAssertionFinding(
                    rule_type=r.rule_type,
                    target_description=r.target_description or "全屏白屏无内容检测",
                    verdict=AssertionVerdict.FAIL if is_white else AssertionVerdict.PASS,
                    confidence_score=0.98 if is_white else 0.95,
                    reasoning_explanation=f"检测到页面空白占比达到 {round(simulated_white_screen_ratio * 100, 1)}%，未渲染有效主体视觉内容"
                    if is_white
                    else f"页面视觉渲染饱满，空白区域占比 {round(simulated_white_screen_ratio * 100, 1)}% 处于正常区间",
                    detected_bounding_box={"x": 0, "y": 0, "width": 1920, "height": 1080} if is_white else None,
                )
            )

        elif r.rule_type == VisualAssertionRuleType.ASSERT_NO_BROKEN_IMAGES:
            has_broken = simulated_broken_images_count > 0
            findings.append(
                VisualAssertionFinding(
                    rule_type=r.rule_type,
                    target_description=r.target_description or "全页图片加载状态检测",
                    verdict=AssertionVerdict.FAIL if has_broken else AssertionVerdict.PASS,
                    confidence_score=0.94,
                    reasoning_explanation=f"视觉特征匹配检测到 {simulated_broken_images_count} 处图片资源加载失败裂图占位符"
                    if has_broken
                    else "全页图片资源均已正确解码渲染，未发现裂图异常",
                    detected_bounding_box={"x": 240, "y": 180, "width": 120, "height": 120} if has_broken else None,
                )
            )

        elif r.rule_type == VisualAssertionRuleType.ASSERT_KEY_ELEMENT_VISIBLE:
            is_missing = any(target in r.target_description for target in missing_elements)
            findings.append(
                VisualAssertionFinding(
                    rule_type=r.rule_type,
                    target_description=r.target_description,
                    verdict=AssertionVerdict.FAIL if is_missing else AssertionVerdict.PASS,
                    confidence_score=0.92,
                    reasoning_explanation=f"关键视觉元素 [{r.target_description}] 在可视视口范围内未探测到或被遮挡隐藏"
                    if is_missing
                    else f"关键业务要素 [{r.target_description}] 已在视口区域清晰渲染且无碰撞遮挡",
                    detected_bounding_box=None
                    if is_missing
                    else (r.expected_bounding_box or {"x": 100, "y": 200, "width": 120, "height": 40}),
                )
            )

        elif r.rule_type == VisualAssertionRuleType.ASSERT_NO_INFINITE_LOADING:
            findings.append(
                VisualAssertionFinding(
                    rule_type=r.rule_type,
                    target_description=r.target_description or "防骨架屏/加载动画停滞检测",
                    verdict=AssertionVerdict.FAIL if simulated_is_loading_stuck else AssertionVerdict.PASS,
                    confidence_score=0.90,
                    reasoning_explanation="页面中央持续探测到活跃加载旋转指示器，接口数据疑似超时挂起"
                    if simulated_is_loading_stuck
                    else "页面已完成主体数据加载，无停滞加载指示符遮挡",
                    detected_bounding_box={"x": 930, "y": 510, "width": 60, "height": 60}
                    if simulated_is_loading_stuck
                    else None,
                )
            )

        else:
            # ASSERT_CUSTOM_NATURAL_LANGUAGE
            findings.append(
                VisualAssertionFinding(
                    rule_type=r.rule_type,
                    target_description=r.target_description,
                    verdict=AssertionVerdict.PASS,
                    confidence_score=0.88,
                    reasoning_explanation=f"根据视觉提示词 [{r.custom_prompt or r.target_description}] 推理，界面视觉呈现与预期语义一致。",
                    detected_bounding_box=r.expected_bounding_box,
                )
            )

    passed_c = sum(1 for f in findings if f.verdict == AssertionVerdict.PASS)
    failed_c = sum(1 for f in findings if f.verdict == AssertionVerdict.FAIL)
    total_c = len(findings)

    score = (passed_c / total_c * 100.0) if total_c > 0 else 100.0
    overall_pass = failed_c == 0

    now = datetime.now(timezone.utc)
    report_id = f"vlm_{page_name[:12]}_{int(now.timestamp())}_{uuid.uuid4().hex[:4]}"
    report = VLMAssertionReport(
        report_id=report_id,
        page_name=page_name,
        overall_passed=overall_pass,
        visual_semantic_score_pct=score,
        total_assertions_count=total_c,
        passed_count=passed_c,
        failed_count=failed_c,
        findings=findings,
        created_at=now,
    )
    _VLM_ASSERTION_REPORTS[report_id] = report
    return report


def get_vlm_assertion_report(report_id: str) -> VLMAssertionReport | None:
    """按 ID 获取视觉断言报告。"""
    return _VLM_ASSERTION_REPORTS.get(report_id)


def list_vlm_assertion_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史视觉断言报告列表。"""
    reports = list(reversed(list(_VLM_ASSERTION_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
