import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models
from app.models.case import CaseSnapshot, CaseStep, TestCase
from app.models.project import Module, Project


def test_case_management_columns_and_relationships_exist():
    load_all_models()

    case_columns = TestCase.__table__.c
    for column_name in (
        "case_code",
        "summary",
        "preconditions",
        "postconditions",
        "priority",
        "case_level",
        "review_status",
        "owner_id",
        "automation_status",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "review_comment",
        "dataset_version",
    ):
        assert column_name in case_columns

    assert TestCase.steps.property.mapper.class_ is CaseStep
    assert TestCase.snapshots.property.mapper.class_ is CaseSnapshot
    assert CaseStep.__table__.c["case_id"].foreign_keys


def test_project_and_module_codes_can_be_persisted():
    load_all_models()

    assert "project_code" in Project.__table__.c
    assert "module_code" in Module.__table__.c


def test_case_snapshot_has_snapshot_payload_column():
    load_all_models()

    assert "snapshot_data" in CaseSnapshot.__table__.c
