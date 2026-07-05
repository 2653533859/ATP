import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


SYSTEM_PAGES = [
    "frontend/src/views/system/StorageManagementView.vue",
    "frontend/src/views/system/DashboardAlertRulesView.vue",
    "frontend/src/views/system/NotificationList.vue",
    "frontend/src/views/system/GlobalVariableLibrary.vue",
    "frontend/src/views/system/AILLMConfigList.vue",
]


def test_core_system_pages_use_shared_page_shell():
    for path in SYSTEM_PAGES:
        content = repo_path(path).read_text(encoding="utf-8")

        assert "page-shell system-page" in content, path
        assert "page-hero" in content, path
        assert "page-title" in content, path
        assert "page-subtitle" in content, path


def test_core_system_pages_use_shared_panels():
    for path in SYSTEM_PAGES:
        content = repo_path(path).read_text(encoding="utf-8")

        assert "table-panel" in content or "page-panel" in content, path
