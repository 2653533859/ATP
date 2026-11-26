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
    layout = repo_path("frontend/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    hub_config = repo_path("frontend/src/layouts/hubConfig.ts").read_text(encoding="utf-8")

    # 系统中心整体只对 admin/engineer 暴露；AI 模型配置与平台治理仅对 admin 暴露
    assert "canAccess(['admin', 'engineer'])" in layout
    assert 'key="/system/environments"' in layout
    assert 'key="/system/config"' in layout
    assert 'v-if="canAccess([\'admin\'])" key="/system/ai-llm-configs"' in layout
    assert "v-if=\"!localMode && canAccess(['admin', 'engineer'])\" key=\"/system/bug-trackers\"" in layout
    assert 'v-if="canAccess([\'admin\'])" key="/system/users"' in layout
    assert 'key="/system/dashboard-alerts"' not in layout

    # 二级聚合入口保持严格角色隔离
    normalized_hub_config = " ".join(hub_config.split())
    assert (
        "path: '/system/startup-config', labelKey: 'menu.system.startup_config', roles: ['admin']"
        in normalized_hub_config
    )
    assert (
        "path: '/system/dashboard-alerts', labelKey: 'menu.system.dashboard_alerts', roles: ['admin']"
        in normalized_hub_config
    )
    assert (
        "path: '/system/remote-nodes', labelKey: 'menu.system_center.remote_nodes', roles: ['admin']"
        in normalized_hub_config
    )


def test_case_list_exposes_disabled_read_only_actions():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "canModifyCases" in content
    assert "canRunCases" in content
    assert "caseCreateDisabledTip" in content
    assert "runDisabledTip(asCase(record))" in content
    assert "case.msg.read_only_role" in content
    # 新建按钮只按角色禁用；模块在点击时由 resolveActiveModuleId 自动解析，缺失时提示而非禁用按钮
    assert ':disabled="!canModifyCases" @click="openCreate(' in content
    assert ':disabled="!selectedModuleId || !canModifyCases"' not in content
    assert "resolveActiveModuleId()" in content
    assert "case.msg.select_module_first" in content
