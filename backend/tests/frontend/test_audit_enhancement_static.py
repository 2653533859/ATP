import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_notification_config_crud_writes_audit_logs():
    content = repo_path("backend/app/api/v1/notifications.py").read_text(encoding="utf-8")

    assert "from app.services.audit import write_audit_log" in content
    assert "notification_config_create" in content
    assert "notification_config_update" in content
    assert "notification_config_delete" in content
    assert 'resource_type="notification_config"' in content


def test_bug_tracker_config_and_run_bug_actions_write_audit_logs():
    content = repo_path("backend/app/api/v1/bug_trackers.py").read_text(encoding="utf-8")

    assert "bug_tracker_create" in content
    assert "bug_tracker_update" in content
    assert "bug_tracker_delete" in content
    assert "run_bug_link" in content
    assert "run_bug_create" in content
    assert "run_bug_create_duplicate" in content
    assert 'resource_type="bug_tracker"' in content
    assert 'resource_type="test_run"' in content


def test_ai_llm_config_crud_writes_audit_logs():
    content = repo_path("backend/app/api/v1/ai_llm_configs.py").read_text(encoding="utf-8")

    assert "from app.services.audit import write_audit_log" in content
    assert "ai_llm_config_create" in content
    assert "ai_llm_config_update" in content
    assert "ai_llm_config_delete" in content
    assert 'resource_type="ai_llm_config"' in content


def test_audit_policy_documents_required_categories_and_secret_rules():
    content = repo_path("docs/audit-log-policy.md").read_text(encoding="utf-8")

    assert "Required Audit Categories" in content
    assert "Permissions" in content
    assert "Execution defect linkage" in content
    assert "Notification config" in content
    assert "Bug tracker config" in content
    assert "AI config" in content
    assert "Never write" in content
    assert "API keys" in content
