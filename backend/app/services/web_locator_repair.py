"""Build safe, reviewable Web locator repair suggestions without mutating assets."""

from __future__ import annotations

from typing import Any

from app.models.web_assets import WebElementAsset

MAX_SUGGESTIONS = 8
_CONFIDENCE = {
    "test_id": 0.95,
    "testid": 0.95,
    "role": 0.90,
    "label": 0.85,
    "placeholder": 0.85,
    "css": 0.75,
    "locator": 0.75,
    "text": 0.65,
    "xpath": 0.45,
}


def build_locator_repair_suggestions(
    asset: WebElementAsset,
    observed_locators: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return bounded candidates for user confirmation; never changes ``asset``."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(locator: Any, reason: str, confidence: float | None = None) -> None:
        if not isinstance(locator, dict):
            return
        strategy = str(locator.get("strategy", "")).strip().lower()
        value = str(locator.get("value", "")).strip()
        if not strategy or not value:
            return
        normalized = {key: value for key, value in locator.items() if key in {"strategy", "value", "name"} and value}
        key = (strategy, value, str(normalized.get("name", "")))
        current = asset.locator if isinstance(asset.locator, dict) else {}
        current_key = (
            str(current.get("strategy", "")).strip().lower(),
            str(current.get("value", "")).strip(),
            str(current.get("name", "")),
        )
        if key == current_key or key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "locator": normalized,
                "confidence": round(confidence if confidence is not None else _CONFIDENCE.get(strategy, 0.4), 2),
                "reason": reason,
            }
        )

    for item in observed_locators or []:
        add(
            item,
            "来自本次失败页面的候选定位器",
            min(0.98, _CONFIDENCE.get(str(item.get("strategy", "")).lower(), 0.4) + 0.03),
        )
    for item in asset.fallback_locators or []:
        add(item, "已有备用定位器")

    current = asset.locator if isinstance(asset.locator, dict) else {}
    strategy = str(current.get("strategy", "")).strip().lower()
    value = str(current.get("value", "")).strip()
    if strategy in {"test_id", "testid"}:
        add(
            {"strategy": "css", "value": f'[data-testid="{value.replace(chr(34), chr(92) + chr(34))}"]'},
            "由 test id 转换为 CSS",
        )
    elif strategy == "role":
        add(
            {"strategy": "css", "value": f'[role="{value.replace(chr(34), chr(92) + chr(34))}"]'},
            "由 ARIA role 转换为 CSS",
        )
    elif strategy == "css" and value.startswith("#") and len(value) > 1:
        add({"strategy": "test_id", "value": value[1:]}, "由稳定 id 候选生成 test id")
    elif strategy == "text":
        add({"strategy": "role", "value": "button", "name": value}, "由文本候选生成按钮 role")

    return sorted(candidates[:MAX_SUGGESTIONS], key=lambda item: item["confidence"], reverse=True)
