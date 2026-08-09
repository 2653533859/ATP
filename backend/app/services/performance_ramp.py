"""Safe expansion of declarative performance auto-ramp options."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class PerformanceRampError(ValueError):
    """Raised when an auto-ramp definition is invalid."""


def expand_auto_ramp(options: dict[str, Any]) -> dict[str, Any]:
    """Convert ``auto_ramp`` into executor-neutral stages.

    The generated stages are consumed by k6/Locust-compatible adapters and
    remain visible in the persisted options snapshot for auditability.
    """

    result = deepcopy(options)
    config = result.get("auto_ramp")
    if not config:
        return result
    if not isinstance(config, dict):
        raise PerformanceRampError("auto_ramp 必须是 JSON 对象")
    try:
        start = int(config.get("start_vus", config.get("start", 1)))
        step = int(config.get("step_vus", config.get("step", 10)))
        maximum = int(config.get("max_vus", config.get("max", 100)))
        ramp_duration = str(config.get("ramp_duration", "30s"))
        hold_duration = str(config.get("hold_duration", "60s"))
    except (TypeError, ValueError) as exc:
        raise PerformanceRampError("auto_ramp 的用户数参数必须是整数") from exc
    if start < 1 or step < 1 or maximum < start:
        raise PerformanceRampError("auto_ramp 必须满足 1 <= start_vus <= max_vus 且 step_vus > 0")
    if len(ramp_duration) > 32 or len(hold_duration) > 32:
        raise PerformanceRampError("auto_ramp 阶段时长格式过长")

    stages: list[dict[str, Any]] = []
    current = start
    while current < maximum:
        stages.append({"duration": ramp_duration, "target": current})
        current = min(maximum, current + step)
    stages.append({"duration": hold_duration, "target": maximum})
    if len(stages) > 100:
        raise PerformanceRampError("auto_ramp 阶段数量不能超过 100")
    result["stages"] = stages
    result["auto_ramp"] = {**config, "generated_stage_count": len(stages)}
    result.pop("vus", None)
    result.pop("users", None)
    result.pop("concurrency", None)
    return result
