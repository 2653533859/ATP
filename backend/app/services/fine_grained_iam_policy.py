"""Fine-Grained RBAC & Resource Action Access Control Policy Service (T4.2).

Provides:
1. Granular resource taxonomy (case, suite, plan, device, secret, dataset, mesh_chaos).
2. Action taxonomy (read, execute, create, modify, delete, manage_permissions).
3. Enterprise Policy Decision Point (PDP) supporting Allow / Explicit Deny rules.
4. Cross-project horizontal isolation guard (anti-IDOR protection).
5. Dynamic project role (owner, editor, viewer) and system role (admin, engineer, tester) rule evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
import logging
from typing import Any

from app.models.user import UserRole
from app.models.user_project import ProjectRole

logger = logging.getLogger(__name__)


class ResourceKind(str, enum.Enum):
    CASE = "case"
    SUITE = "suite"
    PLAN = "plan"
    DEVICE = "device"
    SECRET = "secret"
    DATASET = "dataset"
    CHAOS = "mesh_chaos"


class IamAction(str, enum.Enum):
    READ = "read"
    EXECUTE = "execute"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    MANAGE_PERMISSIONS = "manage_permissions"


@dataclass
class PolicyRule:
    rule_id: str
    effect: str  # "allow" | "deny"
    principals: list[str]  # e.g. ["role:admin", "project:owner", "project:editor"]
    resources: list[str]  # e.g. ["case:*", "secret:*", "*"]
    actions: list[str]  # e.g. ["read", "modify", "*"]
    description: str = ""
    enabled: bool = True

    def matches_principal(self, user_role: UserRole, project_role: ProjectRole | None) -> bool:
        """Check if rule applies to the caller's global or project role."""
        if "*" in self.principals:
            return True
        if user_role == UserRole.admin:
            return "role:admin" in self.principals or "project:owner" in self.principals

        # For non-admin, if project_role is specified, project_role is the effective authority in the project
        if project_role is not None:
            return f"project:{project_role.value}" in self.principals

        # Outside project context, fall back to global role
        return f"role:{user_role.value}" in self.principals

    def matches_resource_and_action(self, resource_kind: str, action: str) -> bool:
        """Check if rule matches the requested resource type and action."""
        # Action match
        action_match = (
            "*" in self.actions or action in self.actions or IamAction.READ.value in self.actions and action == "read"
        )
        if not action_match:
            return False

        # Resource match
        if "*" in self.resources or f"{resource_kind}:*" in self.resources or resource_kind in self.resources:
            return True
        return False


@dataclass
class IamEvaluationResult:
    allowed: bool
    decision_reason: str
    matched_rule: str | None = None
    resource_kind: str = ""
    action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "decision_reason": self.decision_reason,
            "matched_rule": self.matched_rule,
            "resource_kind": self.resource_kind,
            "action": self.action,
        }


# Enterprise Default Policy Baseline (Hardened Least-Privilege Architecture)
_DEFAULT_POLICY_RULES: list[PolicyRule] = [
    # 1. Global Admin and Project Owner have full unrestricted access
    PolicyRule(
        rule_id="rule_admin_all_allow",
        effect="allow",
        principals=["role:admin", "project:owner"],
        resources=["*"],
        actions=["*"],
        description="系统管理员与项目拥有者拥有无限制完全操作权限",
    ),
    # 2. Project Editor / Engineer can read, create, modify, execute cases/suites/devices/plans
    PolicyRule(
        rule_id="rule_editor_core_ops_allow",
        effect="allow",
        principals=["role:engineer", "project:editor"],
        resources=["case:*", "suite:*", "plan:*", "device:*", "dataset:*", "mesh_chaos:*"],
        actions=["read", "create", "modify", "execute"],
        description="研发工程师与项目编辑者可读写与执行核心资产",
    ),
    # 3. Project Editor cannot delete sensitive shared secrets or manage permissions
    PolicyRule(
        rule_id="rule_editor_secret_delete_deny",
        effect="deny",
        principals=["role:engineer", "project:editor"],
        resources=["secret:*"],
        actions=["delete", "manage_permissions"],
        description="非项目管理员禁止删除企业级密钥与修改权限分配",
    ),
    # 4. Project Viewer / Tester can read cases, suites, and execute test cases
    PolicyRule(
        rule_id="rule_viewer_read_allow",
        effect="allow",
        principals=["role:tester", "project:viewer"],
        resources=["case:*", "suite:*", "plan:*", "dataset:*"],
        actions=["read", "execute"],
        description="测试人员与访客可只读访问用例与触发常规测试执行",
    ),
    # 5. Explicit Deny: Viewers / Testers cannot modify or delete any asset
    PolicyRule(
        rule_id="rule_viewer_mutation_deny",
        effect="deny",
        principals=["role:tester", "project:viewer"],
        resources=["*"],
        actions=["create", "modify", "delete", "manage_permissions"],
        description="访客与普通测试人员严禁修改或删除项目资产",
    ),
    # 6. Explicit Deny: Viewers / Testers cannot access enterprise secrets
    PolicyRule(
        rule_id="rule_viewer_secret_deny",
        effect="deny",
        principals=["role:tester", "project:viewer"],
        resources=["secret:*"],
        actions=["*"],
        description="严禁普通访客直接窥探企业级密钥与凭证",
    ),
]

_CUSTOM_RULES: list[PolicyRule] = []


def register_custom_policy(rule: PolicyRule) -> None:
    """Register custom enterprise policy rule."""
    _CUSTOM_RULES.append(rule)


def list_effective_policies() -> list[PolicyRule]:
    """Retrieve all effective policy rules."""
    return _DEFAULT_POLICY_RULES + _CUSTOM_RULES


def evaluate_iam_policy(
    user_role: UserRole,
    project_role: ProjectRole | None,
    resource_kind: str,
    action: str,
    *,
    project_id: int | None = None,
    resource_project_id: int | None = None,
) -> IamEvaluationResult:
    """Policy Decision Point (PDP): evaluates fine-grained access with explicit deny precedence."""
    # 1. Anti-IDOR: Check cross-project boundary isolation
    if project_id is not None and resource_project_id is not None:
        if project_id != resource_project_id and user_role != UserRole.admin:
            return IamEvaluationResult(
                allowed=False,
                decision_reason=f"跨项目隔离拦截: 请求项目 ({project_id}) 与目标资源所属项目 ({resource_project_id}) 不符",
                matched_rule="anti_idor_cross_project_isolation",
                resource_kind=resource_kind,
                action=action,
            )

    # 2. Iterate policies: Deny rules take immediate precedence
    all_rules = list_effective_policies()

    # Pass A: Check explicit DENY rules first
    for rule in all_rules:
        if not rule.enabled:
            continue
        if rule.effect == "deny":
            if rule.matches_principal(user_role, project_role) and rule.matches_resource_and_action(
                resource_kind, action
            ):
                return IamEvaluationResult(
                    allowed=False,
                    decision_reason=f"策略显式拒绝 (Explicit Deny): {rule.description or rule.rule_id}",
                    matched_rule=rule.rule_id,
                    resource_kind=resource_kind,
                    action=action,
                )

    # Pass B: Check explicit ALLOW rules
    for rule in all_rules:
        if not rule.enabled:
            continue
        if rule.effect == "allow":
            if rule.matches_principal(user_role, project_role) and rule.matches_resource_and_action(
                resource_kind, action
            ):
                return IamEvaluationResult(
                    allowed=True,
                    decision_reason=f"策略允许 (Explicit Allow): {rule.description or rule.rule_id}",
                    matched_rule=rule.rule_id,
                    resource_kind=resource_kind,
                    action=action,
                )

    # Pass C: Default Deny (Least Privilege)
    return IamEvaluationResult(
        allowed=False,
        decision_reason=f"默认拒绝 (Default Deny): 未匹配到允许角色执行 {resource_kind}:{action} 操作的显式策略",
        matched_rule=None,
        resource_kind=resource_kind,
        action=action,
    )
