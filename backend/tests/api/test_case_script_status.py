"""Regression tests for case provenance and script status fields."""

from datetime import datetime, timezone

from app.models.case import CaseStatus, CaseType, TestCase
from app.schemas.case import TestCaseOut

from app.models.bootstrap import load_all_models

load_all_models()


def _case(case_type: CaseType, config: dict | None = None) -> TestCase:
    return TestCase(
        id=1,
        name="generated case",
        case_code="CASE-1",
        summary="summary",
        case_type=case_type,
        status=CaseStatus.draft,
        priority="P2",
        case_level="regression",
        review_status="pending",
        automation_status="auto",
        tags=[],
        module_id=1,
        creator_id=1,
        config=config or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_ai_generated_web_case_with_script_is_marked_generated():
    case = _case(CaseType.web, {"_ai_generated": True, "script_path": "scripts/cases/1/script.py"})

    assert case.ai_generated is True
    assert case.script_status == "generated"
    payload = TestCaseOut.model_validate(case)
    assert payload.ai_generated is True
    assert payload.script_status == "generated"


def test_ai_generated_android_case_without_script_is_marked_missing():
    case = _case(CaseType.android, {"_ai_generated": True})

    assert case.ai_generated is True
    assert case.script_status == "missing"


def test_api_case_script_status_is_not_applicable():
    case = _case(CaseType.api, {"_ai_generated": True})

    assert case.ai_generated is True
    assert case.script_status == "not_applicable"
