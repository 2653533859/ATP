"""Regression tests for the explicit Hermes acceptance command."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "hermes-evaluation-acceptance.py"


def _module():
    spec = importlib.util.spec_from_file_location("hermes_evaluation_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _question(case_id="grounded-evidence", execution="query", **overrides):
    question = {
        "id": case_id,
        "prompt": "固定题",
        "execution": execution,
        "expected_refusal": False,
        "expected_tools": [],
        "expected_source_types": [],
        "required_answer_terms": [],
    }
    question.update(overrides)
    return question


def _step(tool, status="ok", evidence=True):
    return {"tool": tool, "status": status, "evidence": [{"evidence_id": "safe"}] if evidence else []}


def _evaluation(module, question, scores):
    return {
        "set_id": module.EXPECTED_SET_ID,
        "set_version": module.EXPECTED_SET_VERSION,
        "case_id": question["id"],
        "scores": scores,
    }


def test_base_url_rejects_embedded_credentials_and_query():
    module = _module()
    with pytest.raises(module.AcceptanceError):
        module.ApiClient("https://user:secret@example.test/api/v1")
    with pytest.raises(module.AcceptanceError):
        module.ApiClient("https://example.test/api/v1?token=secret")
    assert module.ApiClient("https://example.test/api/v1/").base_url == "https://example.test/api/v1"


@pytest.mark.parametrize(
    ("mode", "sources", "citation", "expected_status"),
    [
        ("no_results", [], False, "blocked"),
        ("project_retrieval", [{"source_type": "requirement", "match_score": 1}], False, "failed"),
        ("llm_grounded", [{"source_type": "knowledge", "match_score": 1}], True, "blocked"),
        ("llm_grounded", [{"source_type": "requirement", "match_score": 1}], True, "passed"),
    ],
)
def test_positive_query_requires_fixture_model_and_relevant_citation(mode, sources, citation, expected_status):
    module = _module()
    question = _question(expected_source_types=["requirement"])
    response = {
        "mode": mode,
        "sources": sources,
        "evaluation": _evaluation(module, question, {"citation_relevance": citation, "refusal_correctness": True}),
        "answer": "private project data must not enter the report",
    }
    result = module.assess_case(question, response)
    assert result["status"] == expected_status
    assert "private project data" not in json.dumps(result)


def test_refusal_and_tool_statuses_have_distinct_pass_block_fail_outcomes():
    module = _module()
    refusal = _question("missing-evidence", expected_refusal=True)
    assert (
        module.assess_case(
            refusal,
            {
                "mode": "no_results",
                "evaluation": _evaluation(module, refusal, {"refusal_correctness": True, "answer_completeness": True}),
            },
        )["status"]
        == "passed"
    )
    tool_question = _question(
        "failed-and-quality",
        "orchestrate",
        expected_tools=["failed_tasks", "quality_trend"],
        required_answer_terms=["失败任务", "质量趋势"],
    )
    base = {
        "status": "matched",
        "evaluation": _evaluation(
            module, tool_question, {"tool_selection": True, "answer_completeness": True, "refusal_correctness": True}
        ),
    }
    assert (
        module.assess_case(tool_question, {**base, "steps": [_step("failed_tasks"), _step("quality_trend")]})["status"]
        == "passed"
    )
    assert (
        module.assess_case(
            tool_question, {**base, "steps": [_step("failed_tasks"), _step("quality_trend", "not_found", False)]}
        )["status"]
        == "blocked"
    )
    assert (
        module.assess_case(
            tool_question, {**base, "steps": [_step("failed_tasks"), _step("quality_trend", "timeout", False)]}
        )["status"]
        == "failed"
    )
    assert (
        module.assess_case(
            tool_question, {**base, "steps": [_step("failed_tasks"), _step("quality_trend", "ok", False)]}
        )["status"]
        == "failed"
    )


def test_preflight_only_reads_metadata_and_reports_model_gate():
    module = _module()

    class Client:
        def __init__(self, bound):
            self.bound = bound
            self.calls = []

        def request(self, method, path, payload=None):
            self.calls.append((method, path))
            assert method == "GET" and payload is None
            if path == "/projects/7":
                return {"id": 7, "ai_llm_config_id": 3 if self.bound else None}
            return {
                "id": module.EXPECTED_SET_ID,
                "version": module.EXPECTED_SET_VERSION,
                "questions": [_question(case_id) for case_id in sorted(module.EXPECTED_CASE_IDS)],
            }

    unbound = Client(False)
    assert module.run(unbound, 7, execute=False)["reason"] == "project_model_not_bound"
    bound = Client(True)
    assert module.run(bound, 7, execute=False)["status"] == "pending_fixture_review"
    assert len(bound.calls) == 2


def test_planner_challenge_requires_real_model_plan_and_tool_evidence():
    module = _module()
    response = {
        "planner": {"source": "model", "validation": "accepted", "model_calls": 1},
        "steps": [_step("failed_tasks"), _step("quality_trend")],
        "answer": "secret project answer",
    }
    assert module.assess_planner(response)["status"] == "passed"
    assert module.assess_planner({**response, "planner": {"source": "deterministic"}})["status"] == "failed"
    assert (
        module.assess_planner({**response, "steps": [_step("failed_tasks"), _step("quality_trend", "empty", False)]})[
            "status"
        ]
        == "blocked"
    )
    assert "secret" not in json.dumps(module.assess_planner(response))


def test_planner_challenge_bypasses_the_deterministic_router():
    module = _module()
    from app.services.hermes_orchestration import plan_read_tools

    assert plan_read_tools(module.PLANNER_CHALLENGE).status == "no_match"


def test_case_rejects_a_score_from_another_set_version():
    module = _module()
    question = _question(expected_source_types=["requirement"])
    evaluation = _evaluation(module, question, {"citation_relevance": True, "refusal_correctness": True})
    evaluation["set_version"] = "old-version"
    result = module.assess_case(
        question,
        {
            "mode": "llm_grounded",
            "sources": [{"source_type": "requirement", "match_score": 1}],
            "evaluation": evaluation,
        },
    )
    assert result["status"] == "failed"


def test_execute_uses_isolated_conversations_and_never_records_answer_text():
    module = _module()
    questions = [
        _question("grounded-evidence"),
        _question("requirement-evidence", expected_source_types=["requirement"]),
        _question("missing-evidence", expected_refusal=True),
        _question("prompt-injection-refusal", expected_refusal=True),
    ]
    questions.extend(
        _question(case_id, "orchestrate", expected_tools=["failed_tasks"])
        for case_id in (
            "failed-task-triage",
            "quality-summary",
            "failed-and-quality",
            "run-detail",
            "requirement-links",
            "knowledge-detail",
        )
    )
    for question in questions:
        question["prompt"] += question["id"]
    by_prompt = {question["prompt"]: question for question in questions}

    class Client:
        def __init__(self):
            self.posted = []

        def request(self, method, path, payload=None):
            if method == "GET" and path == "/hermes/governance/evaluation-set":
                return {"id": module.EXPECTED_SET_ID, "version": module.EXPECTED_SET_VERSION, "questions": questions}
            if method == "GET" and path == "/projects/7":
                return {"id": 7, "ai_llm_config_id": 3}
            self.posted.append((path, payload))
            if payload["query"] == module.PLANNER_CHALLENGE:
                return {
                    "planner": {"source": "model", "validation": "accepted", "model_calls": 1},
                    "steps": [_step("failed_tasks"), _step("quality_trend")],
                    "answer": "hidden model answer",
                }
            question = by_prompt[payload["query"]]
            if question["execution"] == "orchestrate":
                return {
                    "status": "matched",
                    "steps": [_step("failed_tasks")],
                    "evaluation": _evaluation(module, question, {"tool_selection": True, "refusal_correctness": True}),
                    "answer": "hidden tool answer",
                }
            if question["expected_refusal"]:
                return {
                    "mode": "no_results",
                    "evaluation": _evaluation(
                        module, question, {"refusal_correctness": True, "answer_completeness": True}
                    ),
                    "answer": "hidden refusal answer",
                }
            return {
                "mode": "llm_grounded",
                "sources": [{"source_type": "requirement", "match_score": 1, "excerpt": "private source"}],
                "evaluation": _evaluation(module, question, {"citation_relevance": True, "refusal_correctness": True}),
                "answer": "hidden grounded answer",
            }

    client = Client()
    report = module.run(client, 7, execute=True)
    assert report["status"] == "passed"
    assert report["summary"] == {"passed": 10, "blocked": 0, "failed": 0}
    assert len(client.posted) == 11
    assert len({payload["conversation_id"] for _path, payload in client.posted}) == 11
    assert "hidden" not in json.dumps(report)
    assert "private source" not in json.dumps(report)
