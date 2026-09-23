#!/usr/bin/env python3
"""Run a bounded Hermes evaluation against an explicitly selected project.

The default mode reads metadata only. --execute creates Hermes sessions and may
call the project's model; it never creates, changes or deletes business assets.
Reports contain only structural results, never answers or source bodies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from uuid import uuid4


EXPECTED_SET_ID = "hermes-core-v2"
EXPECTED_SET_VERSION = "2026-09-23.1"
EXPECTED_CASE_IDS = {
    "grounded-evidence",
    "failed-task-triage",
    "quality-summary",
    "failed-and-quality",
    "run-detail",
    "requirement-links",
    "knowledge-detail",
    "requirement-evidence",
    "missing-evidence",
    "prompt-injection-refusal",
}
PLANNER_CHALLENGE = "请先找出最需要关注的测试作业，再告诉我最近表现是否有变化。"
PLANNER_EXPECTED_TOOLS = {"failed_tasks", "quality_trend"}
FIXED_ASSETS = ["case run 1", "requirement 1", "knowledge 1", "matching login evidence"]
_MODES = {"llm_grounded", "project_retrieval", "no_results"}
_TOOL_STATUSES = {"ok", "empty", "not_found", "timeout", "error"}


class AcceptanceError(RuntimeError):
    """A failure safe to include in a report."""


def _base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AcceptanceError("base URL must be http(s) without credentials, query or fragment")
    try:
        port = parsed.port
    except ValueError:
        raise AcceptanceError("base URL has an invalid port") from None
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    suffix = f":{port}" if port is not None else ""
    return f"{parsed.scheme}://{host}{suffix}{parsed.path.rstrip('/')}"


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 90):
        self.base_url = _base_url(base_url)
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise AcceptanceError("invalid API path")
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=self.headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024)
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            exc.read()
            raise AcceptanceError(f"{method} {path} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError, TimeoutError, ValueError, UnicodeError):
            raise AcceptanceError(f"{method} {path} request failed") from None

    def login(self, username: str, password: str) -> None:
        response = self.request("POST", "/auth/login", {"username": username, "password": password})
        if not isinstance(response, dict) or not isinstance(response.get("access_token"), str):
            raise AcceptanceError("login response has no access token")
        self.headers["Authorization"] = f"Bearer {response['access_token']}"


def _safe_enum(value: Any, allowed: set[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "unknown"


def _relevant_sources(question: dict[str, Any], response: dict[str, Any]) -> bool:
    expected_types = set(question.get("expected_source_types") or [])
    sources = response.get("sources")
    if not isinstance(sources, list):
        return False
    return any(
        isinstance(source, dict)
        and isinstance(source.get("match_score"), int)
        and source["match_score"] > 0
        and (not expected_types or source.get("source_type") in expected_types)
        for source in sources
    )


def _scores(question: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    evaluation = response.get("evaluation")
    if not isinstance(evaluation, dict) or any(
        evaluation.get(key) != expected
        for key, expected in (
            ("set_id", EXPECTED_SET_ID),
            ("set_version", EXPECTED_SET_VERSION),
            ("case_id", question["id"]),
        )
    ):
        return {}
    scores = evaluation.get("scores")
    return scores if isinstance(scores, dict) else {}


def assess_case(question: dict[str, Any], response: Any) -> dict[str, Any]:
    case_id = question["id"]
    execution = question["execution"]
    result: dict[str, Any] = {"case_id": case_id, "execution": execution, "status": "failed"}
    if not isinstance(response, dict):
        result["reason"] = "invalid_response"
        return result
    if isinstance(response.get("session_id"), int) and response["session_id"] > 0:
        result["session_id"] = response["session_id"]
    result["mode"] = _safe_enum(response.get("mode"), _MODES) if execution == "query" else None
    scores = _scores(question, response)
    if execution == "query":
        if question["expected_refusal"]:
            valid = response.get("mode") == "no_results" and scores.get("refusal_correctness") is True
            valid = valid and scores.get("answer_completeness") is True
            result.update(status="passed" if valid else "failed", reason="refusal_ok" if valid else "refusal_wrong")
        elif not _relevant_sources(question, response):
            result.update(status="blocked", reason="required_source_missing")
        else:
            valid = (
                response.get("mode") == "llm_grounded"
                and scores.get("citation_relevance") is True
                and scores.get("refusal_correctness") is True
            )
            result.update(
                status="passed" if valid else "failed", reason="grounded_ok" if valid else "model_or_citation_failed"
            )
        return result

    steps = response.get("steps")
    if not isinstance(steps, list):
        result["reason"] = "invalid_steps"
        return result
    expected_tools = set(question.get("expected_tools") or [])
    actual_tools = [step.get("tool") for step in steps if isinstance(step, dict)]
    result["tool_statuses"] = [
        _safe_enum(step.get("status"), _TOOL_STATUSES) if isinstance(step, dict) else "unknown" for step in steps
    ]
    if (
        response.get("status") != "matched"
        or len(actual_tools) != len(expected_tools)
        or set(actual_tools) != expected_tools
    ):
        result["reason"] = "tool_selection_wrong"
        return result
    if any(status in {"empty", "not_found"} for status in result["tool_statuses"]):
        result.update(status="blocked", reason="required_tool_data_missing")
        return result
    if any(status != "ok" for status in result["tool_statuses"]):
        result["reason"] = "tool_execution_failed"
        return result
    if any(not isinstance(step.get("evidence"), list) or not step["evidence"] for step in steps):
        result["reason"] = "tool_evidence_missing"
        return result
    valid = scores.get("tool_selection") is True and scores.get("refusal_correctness") is True
    if question.get("required_answer_terms"):
        valid = valid and scores.get("answer_completeness") is True
    result.update(status="passed" if valid else "failed", reason="tools_ok" if valid else "score_failed")
    return result


def assess_planner(response: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"case_id": "model-planner-challenge", "execution": "orchestrate", "status": "failed"}
    if not isinstance(response, dict) or not isinstance(response.get("planner"), dict):
        result["reason"] = "invalid_response"
        return result
    if isinstance(response.get("session_id"), int) and response["session_id"] > 0:
        result["session_id"] = response["session_id"]
    planner = response["planner"]
    if not (
        planner.get("source") == "model" and planner.get("validation") == "accepted" and planner.get("model_calls") == 1
    ):
        result["reason"] = "model_plan_not_accepted"
        return result
    steps = response.get("steps")
    if not isinstance(steps, list) or len(steps) != len(PLANNER_EXPECTED_TOOLS):
        result["reason"] = "tool_selection_wrong"
        return result
    if {step.get("tool") for step in steps if isinstance(step, dict)} != PLANNER_EXPECTED_TOOLS:
        result["reason"] = "tool_selection_wrong"
        return result
    statuses = [step.get("status") if isinstance(step, dict) else None for step in steps]
    result["tool_statuses"] = [_safe_enum(status, _TOOL_STATUSES) for status in statuses]
    if any(status in {"empty", "not_found"} for status in statuses):
        result.update(status="blocked", reason="required_tool_data_missing")
    elif any(status != "ok" for status in statuses):
        result["reason"] = "tool_execution_failed"
    elif any(not isinstance(step.get("evidence"), list) or not step["evidence"] for step in steps):
        result["reason"] = "tool_evidence_missing"
    else:
        result.update(status="passed", reason="model_plan_ok")
    return result


def run(client: ApiClient, project_id: int, *, execute: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "evidence_type": "hermes_evaluation_acceptance",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "mode": "execute" if execute else "preflight",
        "status": "blocked",
        "fixed_asset_requirements": FIXED_ASSETS,
        "cases": [],
    }
    evaluation_set = client.request("GET", "/hermes/governance/evaluation-set")
    project = client.request("GET", f"/projects/{project_id}")
    if not isinstance(evaluation_set, dict) or not isinstance(project, dict):
        raise AcceptanceError("evaluation set or project response has an invalid shape")
    if project.get("id") != project_id:
        raise AcceptanceError("project response does not match the selected project")
    report["evaluation_set"] = {
        "id": evaluation_set.get("id"),
        "version": evaluation_set.get("version"),
        "size": len(evaluation_set.get("questions", [])) if isinstance(evaluation_set.get("questions"), list) else 0,
    }
    report["model_bound"] = isinstance(project.get("ai_llm_config_id"), int) and project["ai_llm_config_id"] > 0
    questions = evaluation_set.get("questions")
    if (
        evaluation_set.get("id") != EXPECTED_SET_ID
        or evaluation_set.get("version") != EXPECTED_SET_VERSION
        or not isinstance(questions, list)
        or len(questions) != 10
    ):
        report["reason"] = "evaluation_set_version_mismatch"
        return report
    if (
        any(
            not isinstance(question, dict)
            or not isinstance(question.get("id"), str)
            or not isinstance(question.get("prompt"), str)
            or not 1 <= len(question["prompt"]) <= 2_000
            or question.get("execution") not in {"query", "orchestrate"}
            or not isinstance(question.get("expected_refusal"), bool)
            or not isinstance(question.get("expected_tools"), list)
            or not isinstance(question.get("expected_source_types"), list)
            or not isinstance(question.get("required_answer_terms"), list)
            for question in questions
        )
        or {question["id"] for question in questions} != EXPECTED_CASE_IDS
    ):
        report["reason"] = "evaluation_set_shape_mismatch"
        return report
    if not report["model_bound"]:
        report["reason"] = "project_model_not_bound"
        return report
    if not execute:
        report.update(status="pending_fixture_review", reason="fixed_assets_not_verified")
        return report
    for question in questions:
        path = f"/hermes/{question['execution']}"
        try:
            response = client.request(
                "POST",
                path,
                {
                    "project_id": project_id,
                    "query": question["prompt"],
                    "conversation_id": f"hermes-eval-{uuid4().hex}",
                },
            )
            report["cases"].append(assess_case(question, response))
        except AcceptanceError:
            report["cases"].append(
                {
                    "case_id": question["id"],
                    "execution": question["execution"],
                    "status": "failed",
                    "reason": "request_failed",
                }
            )
    try:
        planner_response = client.request(
            "POST",
            "/hermes/orchestrate",
            {
                "project_id": project_id,
                "query": PLANNER_CHALLENGE,
                "conversation_id": f"hermes-eval-{uuid4().hex}",
            },
        )
        report["model_planner"] = assess_planner(planner_response)
    except AcceptanceError:
        report["model_planner"] = {
            "case_id": "model-planner-challenge",
            "status": "failed",
            "reason": "request_failed",
        }
    statuses = {item["status"] for item in report["cases"] + [report["model_planner"]]}
    report["status"] = "failed" if "failed" in statuses else "blocked" if "blocked" in statuses else "passed"
    report["summary"] = {
        status: sum(item["status"] == status for item in report["cases"]) for status in ("passed", "blocked", "failed")
    }
    report["scope"] = (
        "10 fixed cases (6 deterministic tools, 2 no-source refusals, 2 model-eligible queries) plus 1 model-planner challenge"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="API base including /api/v1; no credentials in the URL")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="create Hermes sessions and call the project's model")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args(argv)
    if args.project_id < 1 or args.timeout <= 0:
        parser.error("--project-id and --timeout must be positive")
    try:
        client = ApiClient(args.base_url, token=os.getenv("ATP_TOKEN"), timeout=args.timeout)
        if not os.getenv("ATP_TOKEN"):
            username, password = os.getenv("ATP_USERNAME"), os.getenv("ATP_PASSWORD")
            if not username or not password:
                raise AcceptanceError("set ATP_TOKEN or ATP_USERNAME and ATP_PASSWORD")
            client.login(username, password)
        report = run(client, args.project_id, execute=args.execute)
    except AcceptanceError as exc:
        report = {
            "evidence_type": "hermes_evaluation_acceptance",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "project_id": args.project_id,
            "mode": "execute" if args.execute else "preflight",
            "status": "failed",
            "reason": str(exc),
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Hermes evaluation: {report['status']} (report: {args.report})")
    return 0 if report["status"] in {"passed", "pending_fixture_review"} else 2


if __name__ == "__main__":
    sys.exit(main())
