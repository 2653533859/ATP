"""M0 synthetic vision/JSON probe; never captures or controls a real device."""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.ai_case.llm_client import LLMRequest  # noqa: E402
from app.services.android_agent.contracts import DecisionRejected, validate_context  # noqa: E402
from app.services.android_agent.model_probe import probe_model  # noqa: E402


async def run(endpoint: str, model: str, key: str) -> dict:
    results = []
    for index, expected_node in enumerate(("n1", "n2"), 1):
        image = Image.new("RGB", (480, 240), "white")
        draw = ImageDraw.Draw(image)
        for node, x in (("n1", 20), ("n2", 260)):
            draw.rectangle((x, 60, x + 180, 180), fill="blue" if node == expected_node else "red")
            draw.text((x + 60, 20), node, fill="black", font_size=28)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        observation_id = f"synthetic-{index}"
        observation = {"observation_id": observation_id, "nodes": [{"node_id": "n1"}, {"node_id": "n2"}]}
        request = LLMRequest(
            provider="openai_compatible",
            endpoint=endpoint,
            api_key=key,
            model_name=model,
            prompt="",
            image_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
            temperature=0,
        )
        try:
            result = await probe_model(
                request,
                goal=(
                    "Tap the BLUE rectangle, identified by the node label above it in the attached image. "
                    "Expected post-action condition: element_visible resource_id test:id/result. "
                    "Return exactly one tap proposal. Do not finish or execute anything."
                ),
                observation=observation,
            )
            validate_context(
                result.decision,
                observation_id=observation_id,
                observed_package="test.synthetic",
                allowed_package="test.synthetic",
                captured_epoch=1,
                current_epoch=1,
                controllable_node_ids={"n1", "n2"},
                allowed_value_refs=set(),
                device_online=True,
                observation_available=True,
            )
            target = getattr(result.decision, "target", None)
            correct = result.decision.action == "tap" and target is not None and target.node_id == expected_node
            results.append(
                {
                    "trial": index,
                    "schema_valid": True,
                    "visual_target_correct": correct,
                    "elapsed_ms": result.elapsed_ms,
                    "usage": result.usage,
                }
            )
        except DecisionRejected as exc:
            results.append({"trial": index, "schema_valid": False, "error_code": str(exc)})
    return {
        "model": model,
        "fixture": "synthetic_two_color_buttons_v1",
        "trials": results,
        "device_actions_executed": 0,
        "m0_accepted": False,
        "probe_passed": all(x.get("visual_target_correct") is True for x in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("ATP_AGENT_PROBE_API_KEY")
    if not key:
        parser.error("ATP_AGENT_PROBE_API_KEY must be set in this process environment")
    # Reserve the output before network calls; never overwrite prior evidence.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        report = asyncio.run(run(args.endpoint, args.model, key))
        text = json.dumps(report, ensure_ascii=False, indent=2)
        handle.write(text + "\n")
    print(text)
    return 0 if report["probe_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
