from pathlib import Path


def test_app_startup_imports_notification_model_for_create_all_bootstrap():
    main_file = Path(__file__).resolve().parents[2] / "app" / "main.py"
    content = main_file.read_text(encoding="utf-8")

    assert "from app.models.notification import NotificationConfig" in content


def test_project_model_declares_notification_cascade_relationship():
    project_file = Path(__file__).resolve().parents[2] / "app" / "models" / "project.py"
    content = project_file.read_text(encoding="utf-8")

    assert "notifications" in content
    assert 'cascade="all, delete-orphan"' in content
