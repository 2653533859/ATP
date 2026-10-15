"""Unit tests for T4.2 Fine-Grained RBAC & Resource Action Access Control Policy.

Tests:
1. Admin and Project Owner unrestricted access across all resource actions
2. Engineer / Editor core operations allowed, but secret deletion denied
3. Tester / Viewer read and execute allowed, mutations and secrets denied
4. Anti-IDOR cross-project boundary isolation enforcement
5. Custom policy dynamic registration and explicit deny precedence
"""

from __future__ import annotations

from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.services.fine_grained_iam_policy import (
    PolicyRule,
    evaluate_iam_policy,
    list_effective_policies,
    register_custom_policy,
)


def test_admin_and_owner_full_access():
    # 1. Global Admin
    res_admin = evaluate_iam_policy(
        user_role=UserRole.admin,
        project_role=None,
        resource_kind="case",
        action="delete",
        project_id=1,
        resource_project_id=1,
    )
    assert res_admin.allowed is True
    assert res_admin.matched_rule == "rule_admin_all_allow"

    # 2. Project Owner on Secret deletion
    res_owner = evaluate_iam_policy(
        user_role=UserRole.tester,  # Even if global tester, project owner has full access
        project_role=ProjectRole.owner,
        resource_kind="secret",
        action="delete",
        project_id=2,
        resource_project_id=2,
    )
    assert res_owner.allowed is True


def test_engineer_and_editor_permissions():
    # 1. Engineer can create / modify cases
    res_modify = evaluate_iam_policy(
        user_role=UserRole.engineer,
        project_role=ProjectRole.editor,
        resource_kind="case",
        action="modify",
        project_id=1,
        resource_project_id=1,
    )
    assert res_modify.allowed is True
    assert "核心资产" in res_modify.decision_reason

    # 2. Engineer CANNOT delete sensitive secret (Explicit Deny)
    res_secret_delete = evaluate_iam_policy(
        user_role=UserRole.engineer,
        project_role=ProjectRole.editor,
        resource_kind="secret",
        action="delete",
        project_id=1,
        resource_project_id=1,
    )
    assert res_secret_delete.allowed is False
    assert "Explicit Deny" in res_secret_delete.decision_reason
    assert res_secret_delete.matched_rule == "rule_editor_secret_delete_deny"


def test_tester_and_viewer_permissions():
    # 1. Viewer can read cases
    res_read = evaluate_iam_policy(
        user_role=UserRole.tester,
        project_role=ProjectRole.viewer,
        resource_kind="case",
        action="read",
        project_id=1,
        resource_project_id=1,
    )
    assert res_read.allowed is True

    # 2. Viewer CANNOT modify cases (Explicit Deny)
    res_modify = evaluate_iam_policy(
        user_role=UserRole.tester,
        project_role=ProjectRole.viewer,
        resource_kind="case",
        action="modify",
        project_id=1,
        resource_project_id=1,
    )
    assert res_modify.allowed is False
    assert "Explicit Deny" in res_modify.decision_reason

    # 3. Viewer CANNOT access secrets
    res_secret = evaluate_iam_policy(
        user_role=UserRole.tester,
        project_role=ProjectRole.viewer,
        resource_kind="secret",
        action="read",
        project_id=1,
        resource_project_id=1,
    )
    assert res_secret.allowed is False
    assert res_secret.matched_rule == "rule_viewer_secret_deny"


def test_anti_idor_cross_project_isolation():
    # Caller is in Project 10, but attempts to operate on Project 20's case
    res_idor = evaluate_iam_policy(
        user_role=UserRole.engineer,
        project_role=ProjectRole.editor,
        resource_kind="case",
        action="read",
        project_id=10,
        resource_project_id=20,
    )
    assert res_idor.allowed is False
    assert "跨项目隔离拦截" in res_idor.decision_reason
    assert res_idor.matched_rule == "anti_idor_cross_project_isolation"

    # Global Admin bypasses cross-project restriction
    res_admin_cross = evaluate_iam_policy(
        user_role=UserRole.admin,
        project_role=None,
        resource_kind="case",
        action="read",
        project_id=10,
        resource_project_id=20,
    )
    assert res_admin_cross.allowed is True


def test_custom_policy_registration_and_deny_precedence():
    # Register custom rule: explicitly deny chaos execution on prod device for everyone
    custom_deny_rule = PolicyRule(
        rule_id="custom_deny_prod_chaos",
        effect="deny",
        principals=["*"],
        resources=["mesh_chaos:*"],
        actions=["execute"],
        description="封锁生产环境混沌故障执行",
        enabled=True,
    )
    register_custom_policy(custom_deny_rule)

    policies = list_effective_policies()
    assert any(p.rule_id == "custom_deny_prod_chaos" for p in policies)

    # Even engineer should now be denied
    res_chaos = evaluate_iam_policy(
        user_role=UserRole.engineer,
        project_role=ProjectRole.editor,
        resource_kind="mesh_chaos",
        action="execute",
        project_id=1,
        resource_project_id=1,
    )
    assert res_chaos.allowed is False
    assert res_chaos.matched_rule == "custom_deny_prod_chaos"
