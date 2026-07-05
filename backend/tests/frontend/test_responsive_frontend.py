import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_shared_page_shell_has_mobile_layout_rules():
    content = repo_path("frontend/src/styles/page-shell.css").read_text(encoding="utf-8")

    assert "@media (max-width: 768px)" in content
    assert ".page-hero,\n  .page-toolbar" in content
    assert "flex-direction: column" in content
    assert ".table-panel,\n  .page-panel" in content


def test_main_layout_uses_mobile_overlay_sidebar():
    content = repo_path("frontend/src/layouts/MainLayout.vue").read_text(encoding="utf-8")

    assert "window.matchMedia('(max-width: 768px)').matches" in content
    assert ".app-sider.ant-layout-sider-collapsed" in content
    assert "transform: translateX(-100%)" in content
    assert ".content-card" in content
    assert "padding: 14px" in content


def test_case_list_has_narrow_screen_controls():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "@media (max-width: 640px)" in content
    assert ".toolbar-main :deep(.ant-input-search)" in content
    assert "width: 100% !important" in content
    assert "max-height: 320px" in content


def test_batch_operation_bar_wraps_on_mobile():
    content = repo_path("frontend/src/components/common/BatchOperationBar.vue").read_text(encoding="utf-8")

    assert "flex-wrap: wrap" in content
    assert "@media (max-width: 640px)" in content
    assert "flex-direction: column" in content
