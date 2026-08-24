import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_permission_helpers_define_shared_role_rules():
    content = repo_path("frontend/src/utils/permissions.ts").read_text(encoding="utf-8")

    assert "export type UserRole = 'admin' | 'engineer' | 'tester' | 'viewer'" in content
    assert "export function hasAnyRole" in content
    assert "export function canEditProjectAssets" in content
    assert "['admin', 'engineer']" in content


def test_router_supports_general_role_meta():
    content = repo_path("frontend/src/router/index.ts").read_text(encoding="utf-8")

    assert "meta: { roles: ENGINEER_ONLY }" in content
    assert "meta: { roles: ADMIN_ONLY }" in content
    assert "hasAnyRole(auth.user?.role, allowedRoles)" in content
    assert "to.meta.requireAdmin ? ADMIN_ONLY" in content


def test_layout_hides_non_operable_role_entries():
    content = repo_path("frontend/src/layouts/MainLayout.vue").read_text(encoding="utf-8")

    assert "canAccess(['admin', 'engineer'])" in content
    assert 'key="/system/config"' in content
    assert 'key="/system/ai-llm-configs"' not in content
    assert 'key="/system/dashboard-alerts"' not in content


def test_case_list_exposes_disabled_read_only_actions():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "canModifyCases" in content
    assert "canRunCases" in content
    assert "caseCreateDisabledTip" in content
    assert "runDisabledTip(asCase(record))" in content
    assert "case.msg.read_only_role" in content
    assert ':disabled="!selectedModuleId || !canModifyCases"' in content
