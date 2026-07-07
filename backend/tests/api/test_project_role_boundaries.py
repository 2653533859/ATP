"""P3.C Commit 3 项目内角色边界测试。

覆盖矩阵：
- viewer：可读 list_projects / get_project / list_members；不能 update_project / delete_project / add_member / remove_member
- editor：可创建/编辑资源（create_module / update_module / delete_module）；不能改项目设置（add_member）
- owner：所有操作通过
- 全局 admin：bypass 全部，无需 UserProject 记录
"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        get_json_cache=lambda *a, **kw: None,
        set_json_cache=lambda *a, **kw: None,
        delete_json_cache=lambda *a, **kw: None,
        publish_run_event=lambda *a, **kw: None,
        get_async_redis=lambda *a, **kw: None,
    ),
)
sys.modules.setdefault(
    "jose",
    types.SimpleNamespace(
        JWTError=type("JWTError", (Exception,), {}),
        jwt=types.SimpleNamespace(encode=lambda *a, **kw: "", decode=lambda *a, **kw: {}),
    ),
)
sys.modules.setdefault("passlib", types.SimpleNamespace())
sys.modules.setdefault(
    "passlib.context",
    types.SimpleNamespace(
        CryptContext=lambda *a, **kw: types.SimpleNamespace(hash=lambda x: x, verify=lambda *a, **kw: True)
    ),
)

sys.modules.pop("app.api.deps", None)

from fastapi import HTTPException
import pytest

from app.api import deps
from app.models.bootstrap import load_all_models
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, role_satisfies

load_all_models()


def _user(uid=10, role=UserRole.engineer) -> User:
    return User(id=uid, username=f"u{uid}", email=f"u{uid}@x", hashed_password="x", role=role, is_active=True)


class _FakeDB:
    def __init__(self, role_for: dict[tuple[int, int], ProjectRole] | None = None):
        self.user_projects = role_for or {}
        self.audit_records: list = []

    async def execute(self, stmt):
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()
        import re

        uid_m = re.search(r"user_projects\.user_id\s*=\s*(\d+)", sql)
        pid_m = re.search(r"user_projects\.project_id\s*=\s*(\d+)", sql)
        role = self.user_projects.get((int(uid_m.group(1)), int(pid_m.group(1)))) if uid_m and pid_m else None

        class _R:
            def scalar_one_or_none(_self):
                return role

        return _R()

    def add(self, obj):
        if obj.__class__.__name__ == "AuditLog":
            self.audit_records.append(obj)

    async def flush(self):
        return None


# ========================================================================
# 1. role_satisfies 偏序矩阵
# ========================================================================


def test_role_partial_order():
    """owner ≥ editor ≥ viewer，反向不满足。"""
    assert role_satisfies(ProjectRole.owner, ProjectRole.owner)
    assert role_satisfies(ProjectRole.owner, ProjectRole.editor)
    assert role_satisfies(ProjectRole.owner, ProjectRole.viewer)
    assert role_satisfies(ProjectRole.editor, ProjectRole.editor)
    assert role_satisfies(ProjectRole.editor, ProjectRole.viewer)
    assert role_satisfies(ProjectRole.viewer, ProjectRole.viewer)

    assert not role_satisfies(ProjectRole.viewer, ProjectRole.editor)
    assert not role_satisfies(ProjectRole.viewer, ProjectRole.owner)
    assert not role_satisfies(ProjectRole.editor, ProjectRole.owner)


# ========================================================================
# 2. require_project_access 拒绝/允许矩阵
# ========================================================================


@pytest.mark.parametrize(
    ("user_role", "min_role", "should_pass"),
    [
        # viewer 只能看
        (ProjectRole.viewer, ProjectRole.viewer, True),
        (ProjectRole.viewer, ProjectRole.editor, False),
        (ProjectRole.viewer, ProjectRole.owner, False),
        # editor 可读 + 可写
        (ProjectRole.editor, ProjectRole.viewer, True),
        (ProjectRole.editor, ProjectRole.editor, True),
        (ProjectRole.editor, ProjectRole.owner, False),
        # owner 全通
        (ProjectRole.owner, ProjectRole.viewer, True),
        (ProjectRole.owner, ProjectRole.editor, True),
        (ProjectRole.owner, ProjectRole.owner, True),
    ],
)
def test_require_project_access_matrix(user_role, min_role, should_pass):
    db = _FakeDB({(10, 5): user_role})
    user = _user(uid=10)
    checker = deps.require_project_access(min_role)

    if should_pass:
        result = asyncio.run(checker(project_id=5, current_user=user, db=db))
        assert result is user
        assert db.audit_records == []
    else:
        raised = False
        try:
            asyncio.run(checker(project_id=5, current_user=user, db=db))
        except HTTPException as exc:
            raised = exc.status_code == 403
        assert raised
        assert len(db.audit_records) == 1


# ========================================================================
# 3. assert_project_access 等价矩阵
# ========================================================================


@pytest.mark.parametrize(
    ("user_role", "min_role", "should_pass"),
    [
        (ProjectRole.viewer, ProjectRole.viewer, True),
        (ProjectRole.viewer, ProjectRole.editor, False),
        (ProjectRole.editor, ProjectRole.editor, True),
        (ProjectRole.editor, ProjectRole.owner, False),
        (ProjectRole.owner, ProjectRole.owner, True),
    ],
)
def test_assert_project_access_matrix(user_role, min_role, should_pass):
    db = _FakeDB({(10, 5): user_role})
    user = _user(uid=10)

    if should_pass:
        asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=min_role))
        assert db.audit_records == []
    else:
        raised = False
        try:
            asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=min_role))
        except HTTPException as exc:
            raised = exc.status_code == 403
        assert raised


# ========================================================================
# 4. admin 始终 bypass（即便无 UserProject 记录）
# ========================================================================


@pytest.mark.parametrize(
    "min_role",
    [ProjectRole.viewer, ProjectRole.editor, ProjectRole.owner],
)
def test_admin_bypasses_all_min_roles(min_role):
    db = _FakeDB()  # 故意空，不写 UserProject
    admin = _user(uid=1, role=UserRole.admin)
    checker = deps.require_project_access(min_role)

    result = asyncio.run(checker(project_id=999, current_user=admin, db=db))
    assert result is admin
    assert db.audit_records == []


# ========================================================================
# 5. 非成员尝试任何操作 → 403 + 审计
# ========================================================================


@pytest.mark.parametrize(
    "min_role",
    [ProjectRole.viewer, ProjectRole.editor, ProjectRole.owner],
)
def test_non_member_denied_for_all_levels(min_role):
    db = _FakeDB()
    user = _user(uid=10)
    checker = deps.require_project_access(min_role)

    raised = False
    try:
        asyncio.run(checker(project_id=5, current_user=user, db=db))
    except HTTPException as exc:
        raised = exc.status_code == 403
    assert raised
    assert len(db.audit_records) == 1
    record = db.audit_records[0]
    assert record.action == "access_denied"
    assert record.project_id == 5
    assert record.user_id == 10
    assert f"min_role={min_role.value}" in record.detail
    assert "actual=none" in record.detail


# ========================================================================
# 6. 角色降级语义：editor 操作（editor / owner min）
# ========================================================================


def test_editor_can_edit_but_not_manage_settings():
    db = _FakeDB({(10, 5): ProjectRole.editor})
    user = _user(uid=10)

    # editor min → 通过
    asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=ProjectRole.editor))
    # owner min → 拒绝
    raised = False
    try:
        asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=ProjectRole.owner))
    except HTTPException as exc:
        raised = exc.status_code == 403
    assert raised


def test_viewer_cannot_create_or_modify():
    db = _FakeDB({(10, 5): ProjectRole.viewer})
    user = _user(uid=10)

    asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=ProjectRole.viewer))

    for min_role in (ProjectRole.editor, ProjectRole.owner):
        raised = False
        try:
            asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=min_role))
        except HTTPException as exc:
            raised = exc.status_code == 403
        assert raised
