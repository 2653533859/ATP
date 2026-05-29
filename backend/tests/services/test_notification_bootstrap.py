from pathlib import Path


def test_model_bootstrap_imports_full_metadata_graph():
    bootstrap_file = Path(__file__).resolve().parents[2] / "app" / "models" / "bootstrap.py"
    content = bootstrap_file.read_text(encoding="utf-8")

    expected_modules = [
        "from app.models.user import User, UserRole",
        "from app.models.project import Project, Module",
        "from app.models.case import TestCase, CaseStep, TestRun, StepResult, CaseSnapshot",
        "from app.models.environment import Environment, EnvVariable",
        "from app.models.device import Device",
        "from app.models.apk import Apk",
        "from app.models.suite import TestSuite, SuiteRun",
        "from app.models.notification import NotificationConfig",
        "from app.models.mock import MockRule",
        "from app.models.bug_tracker import BugTracker",
        "from app.models.audit import AuditLog",
        "from app.models.plan import TestPlan, PlanRun",
        "from app.models.mobile_special import (",
        "from app.models.global_variable import GlobalVariable",
    ]

    for expected in expected_modules:
        assert expected in content


def test_app_startup_uses_shared_model_bootstrap():
    main_file = Path(__file__).resolve().parents[2] / "app" / "main.py"
    content = main_file.read_text(encoding="utf-8")

    assert "from app.models.bootstrap import load_all_models" in content
    assert "load_all_models()" in content


def test_bootstrap_db_runs_alembic_upgrade_only():
    bootstrap_file = Path(__file__).resolve().parents[2] / "app" / "bootstrap_db.py"
    content = bootstrap_file.read_text(encoding="utf-8")

    assert "command.upgrade" in content
    assert "load_all_models" not in content


def test_worker_uses_shared_model_bootstrap():
    worker_file = Path(__file__).resolve().parents[2] / "app" / "worker" / "tasks.py"
    content = worker_file.read_text(encoding="utf-8")

    assert "from app.models.bootstrap import load_all_models" in content
    assert "load_all_models()" in content


def test_project_model_declares_notification_cascade_relationship():
    project_file = Path(__file__).resolve().parents[2] / "app" / "models" / "project.py"
    content = project_file.read_text(encoding="utf-8")

    assert "notifications" in content
    assert 'cascade="all, delete-orphan"' in content
