#!/usr/bin/env python3
"""Run a real three-browser Web playback and visual-baseline acceptance.

The command creates project-scoped element, page-object, baseline and case
records, then verifies screenshots, traces, videos and network evidence. Set
``ATP_TOKEN`` or ``ATP_USERNAME``/``ATP_PASSWORD`` for an editor account.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


TERMINAL_STATUSES = {"passed", "failed", "error", "skipped"}


class SmokeError(RuntimeError):
    """A required playback acceptance condition was not met."""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default=os.getenv("ATP_API_BASE_URL"), required=False)
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--module-id", type=int, required=True)
    parser.add_argument("--start-url", required=True)
    parser.add_argument("--element-selector", default="body")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--report", type=Path, default=Path("docs/evidence/web-playback-smoke.json"))
    args = parser.parse_args(argv)
    if not args.api_base_url:
        parser.error("--api-base-url or ATP_API_BASE_URL is required")
    return args


def _redact_url(value: str) -> str:
    parsed = urlsplit(value)
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, netloc, parsed.path, "<redacted>" if parsed.query else "", ""))


def _checked(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise SmokeError(f"{response.request.method} {response.request.url.path} returned HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise SmokeError(f"{response.request.method} {response.request.url.path} returned a non-object response")
    return payload


def _poll_run(client: httpx.Client, run_id: int, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        payload = _checked(client.get(f"/runs/{run_id}"))
        if payload.get("status") in TERMINAL_STATUSES:
            return payload
        if time.monotonic() >= deadline:
            raise SmokeError(f"run {run_id} did not finish before the timeout")
        time.sleep(1)


def _create_case(client: httpx.Client, module_id: int, name: str, config: dict[str, Any]) -> dict[str, Any]:
    case = _checked(
        client.post(
            "/cases",
            json={
                "name": name,
                "description": "Current-release Web playback acceptance",
                "case_type": "web",
                "module_id": module_id,
                "tags": ["web-playback", "acceptance"],
                "automation_status": "auto",
                "config": config,
            },
        )
    )
    _checked(client.post(f"/cases/{case['id']}/approve", json={"comment": "Controlled Web playback acceptance"}))
    return case


def _authenticate(client: httpx.Client) -> None:
    token = os.getenv("ATP_TOKEN")
    if token:
        client.headers["Authorization"] = f"Bearer {token}"
        return
    username = os.getenv("ATP_USERNAME")
    password = os.getenv("ATP_PASSWORD")
    if not username or not password:
        raise SmokeError("set ATP_TOKEN or ATP_USERNAME and ATP_PASSWORD")
    response = _checked(client.post("/auth/login", json={"username": username, "password": password}))
    if isinstance(response.get("access_token"), str):
        client.headers["Authorization"] = f"Bearer {response['access_token']}"


def _require_child_evidence(child: dict[str, Any]) -> dict[str, Any]:
    steps = child.get("steps") or []
    summary = child.get("result_summary") or {}
    if child.get("status") != "passed" or len(steps) != 2:
        raise SmokeError(f"browser child run {child.get('id')} failed")
    if not summary.get("trace_url") or not summary.get("video_url"):
        raise SmokeError(f"browser child run {child.get('id')} omitted trace or video evidence")
    if not all(step.get("screenshot_url") for step in steps):
        raise SmokeError(f"browser child run {child.get('id')} omitted step screenshots")
    return {
        "run_id": child["id"],
        "status": child["status"],
        "step_count": len(steps),
        "screenshot_count": sum(bool(step.get("screenshot_url")) for step in steps),
        "trace": True,
        "video": True,
        "network_event_count": len(summary.get("network_events") or []),
    }


def _require_visual_evidence(visual: dict[str, Any]) -> None:
    steps = visual.get("steps") or []
    summary = visual.get("result_summary") or {}
    comparison = steps[-1].get("response_data") if steps else None
    if visual.get("status") != "passed" or len(steps) != 2:
        raise SmokeError(f"visual run {visual.get('id')} failed")
    if not summary.get("trace_url") or not summary.get("video_url"):
        raise SmokeError(f"visual run {visual.get('id')} omitted trace or video evidence")
    if not all(step.get("screenshot_url") for step in steps):
        raise SmokeError(f"visual run {visual.get('id')} omitted step screenshots")
    if not isinstance(comparison, dict) or comparison.get("match") is not True:
        raise SmokeError(f"visual run {visual.get('id')} omitted a successful comparison")


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    api_url = str(args.api_base_url).rstrip("/") + "/api/v1"
    with httpx.Client(base_url=api_url, timeout=45) as client:
        _authenticate(client)
        client.headers["X-Requested-With"] = "XMLHttpRequest"

        recording = _checked(
            client.post(
                "/web-recordings",
                json={"project_id": args.project_id, "start_url": args.start_url, "browser": "chromium"},
            )
        )
        try:
            screenshot = client.post(f"/web-recordings/{recording['id']}/screenshot")
            if (
                screenshot.status_code != 200
                or screenshot.headers.get("content-type", "").split(";", 1)[0] != "image/png"
            ):
                raise SmokeError("recording screenshot was not a PNG")
        finally:
            _checked(client.post(f"/web-recordings/{recording['id']}/stop"))

        baseline = _checked(
            client.post(
                f"/projects/{args.project_id}/web-visual-baselines",
                data={
                    "name": f"Playback baseline {stamp}",
                    "page_url": args.start_url,
                    "threshold": "0.01",
                    "pixel_threshold": "12",
                    "ignore_regions": "[]",
                },
                files={"file": ("baseline.png", screenshot.content, "image/png")},
            )
        )
        element = _checked(
            client.post(
                f"/projects/{args.project_id}/web-elements",
                json={
                    "name": f"Playback element {stamp}",
                    "page_url": args.start_url,
                    "locator": {"strategy": "css", "value": args.element_selector},
                    "fallback_locators": [],
                    "description": "Controlled playback acceptance element",
                },
            )
        )
        page_object = _checked(
            client.post(
                f"/projects/{args.project_id}/web-page-objects",
                json={
                    "name": f"Playback page {stamp}",
                    "url_pattern": args.start_url,
                    "description": "Controlled playback acceptance page object",
                    "element_refs": [{"alias": "target", "asset_id": element["id"]}],
                    "actions": [
                        {"action": "assert_visible", "name": "target visible", "alias": "target", "params": {}}
                    ],
                },
            )
        )

        matrix_case = _create_case(
            client,
            args.module_id,
            f"Three-browser playback {stamp}",
            {
                "headless": True,
                "timeout": 30,
                "collect_trace": True,
                "browser_matrix": [
                    {"label": "Chromium", "browser": "chromium", "viewport": {"width": 1280, "height": 720}},
                    {"label": "Firefox", "browser": "firefox", "viewport": {"width": 1280, "height": 720}},
                    {"label": "WebKit", "browser": "webkit", "viewport": {"width": 1280, "height": 720}},
                ],
                "steps": [
                    {"action": "goto", "name": "open target", "params": {"url": args.start_url}},
                    {
                        "action": "page_object",
                        "name": "reuse page object",
                        "params": {"page_object_id": page_object["id"]},
                    },
                ],
            },
        )
        parent = _checked(client.post(f"/cases/{matrix_case['id']}/run", json={"extra_vars": {}}))
        parent = _poll_run(client, int(parent["id"]), args.timeout)
        variants = (parent.get("result_summary") or {}).get("matrix_variants") or []
        if parent.get("status") != "passed" or len(variants) != 3:
            raise SmokeError(f"browser matrix run {parent.get('id')} failed")
        children = [_poll_run(client, int(item["run_id"]), args.timeout) for item in variants]

        visual_case = _create_case(
            client,
            args.module_id,
            f"Visual playback {stamp}",
            {
                "browser": "chromium",
                "headless": True,
                "timeout": 30,
                "collect_trace": True,
                "viewport": {"width": 1280, "height": 720},
                "steps": [
                    {"action": "goto", "name": "open target", "params": {"url": args.start_url}},
                    {
                        "action": "visual_assert",
                        "name": "compare current page",
                        "params": {"baseline_id": baseline["id"], "threshold": 0.01, "pixel_threshold": 12},
                    },
                ],
            },
        )
        visual = _checked(client.post(f"/cases/{visual_case['id']}/run", json={"extra_vars": {}}))
        visual = _poll_run(client, int(visual["id"]), args.timeout)
        _require_visual_evidence(visual)

        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "passed",
            "api_base_url": _redact_url(str(args.api_base_url)),
            "project_id": args.project_id,
            "module_id": args.module_id,
            "target_url": _redact_url(args.start_url),
            "assets": {
                "element_id": element["id"],
                "page_object_id": page_object["id"],
                "baseline_id": baseline["id"],
                "matrix_case_id": matrix_case["id"],
                "visual_case_id": visual_case["id"],
            },
            "matrix": {
                "parent_run_id": parent["id"],
                "status": parent["status"],
                "variants": variants,
                "children": [_require_child_evidence(child) for child in children],
            },
            "visual": {
                "run_id": visual["id"],
                "status": visual["status"],
                "steps": [
                    {
                        "name": step["name"],
                        "status": step["status"],
                        "screenshot": bool(step.get("screenshot_url")),
                        "response_data": step.get("response_data"),
                    }
                    for step in visual.get("steps") or []
                ],
                "trace": bool((visual.get("result_summary") or {}).get("trace_url")),
                "video": bool((visual.get("result_summary") or {}).get("video_url")),
            },
        }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_acceptance(args)
    except (SmokeError, httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
