"""P3.C 依赖单测：get_project_role / require_project_access / assert_project_access。

覆盖：
- admin → 始终 owner
- editor 用户访问 editor min 通过
- viewer 用户访问 editor min 失败 + 写审计
- 无关用户访问失败 + 写审计
- assert_project_access 非路径参数路径同样工作
"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# stub redis / minio 以防 deps 链触发
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

# 本地无 jose / passlib 时兜底 stub
sys.modules.setdefault(
    "jose",
    types.SimpleNamespace(
        JWTError=type("JWTError", (Exception,), {}),
        jwt=types.SimpleNamespace(encode=lambda *a, **kw: "", decode=lambda *a, **kw: {}),
    ),
)
sys.modules.setdefault(
    "passlib",
    types.SimpleNamespace(),
)
sys.modules.setdefault(
    "passlib.context",
    types.SimpleNamespace(
        CryptContext=lambda *a, **kw: types.SimpleNamespace(hash=lambda x: x, verify=lambda *a, **kw: True)
    ),
)

from fastapi import HTTPException

# 其他 api 测试在模块加载期把 app.api.deps stub 成 SimpleNamespace，
# 这里强制清理后再导入真实模块
sys.modules.pop("app.api.deps", None)

from app.api import deps
from app.models.bootstrap import load_all_models
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject, role_satisfies

load_all_models()


class _FakeDB:
    """模拟 select(UserProject.role).where(user_id, project_id) 返回 scalar_one_or_none。"""

    def __init__(self, mapping: dict[tuple[int, int], ProjectRole] | None = None):
        self.mapping = mapping or {}
        self.audit_records: list[dict] = []

    async def execute(self, stmt):
        # stmt = select(UserProject.role).where(user_id == X, project_id == Y)
        # 提取 where 中的常量比较值
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()
        user_id = None
        project_id = None
        # 找 "user_id = N" 和 "project_id = N"
        import re

        m = re.search(r"user_projects\.user_id\s*=\s*(\d+)", sql)
        if m:
            user_id = int(m.group(1))
        m = re.search(r"user_projects\.project_id\s*=\s*(\d+)", sql)
        if m:
            project_id = int(m.group(1))
        role = self.mapping.get((user_id, project_id)) if user_id and project_id else None

        class _R:
            def scalar_one_or_none(self_inner):
                return role

        return _R()

    def add(self, obj):
        # 捕获写审计
        from app.models.audit import AuditLog

        if isinstance(obj, AuditLog):
            self.audit_records.append(
                {
                    "action": obj.action,
                    "resource_type": obj.resource_type,
                    "project_id": obj.project_id,
                    "user_id": obj.user_id,
                    "detail": obj.detail,
                }
            )

    async def flush(self):
        return None


def _user(role=UserRole.engineer, uid=10) -> User:
    return User(id=uid, username=f"u{uid}", email=f"u{uid}@x", hashed_password="x", role=role, is_active=True)


def test_role_rank_and_satisfies():
    assert role_satisfies(ProjectRole.owner, ProjectRole.viewer)
    assert role_satisfies(ProjectRole.editor, ProjectRole.viewer)
    assert role_satisfies(ProjectRole.editor, ProjectRole.editor)
    assert not role_satisfies(ProjectRole.viewer, ProjectRole.editor)
    assert not role_satisfies(ProjectRole.editor, ProjectRole.owner)


def test_get_project_role_admin_returns_owner_without_lookup():
    db = _FakeDB()  # 即便无 UserProject 记录
    user = _user(role=UserRole.admin, uid=1)
    role = asyncio.run(deps.get_project_role(db, user, project_id=99))
    assert role == ProjectRole.owner


def test_get_project_role_returns_assigned_role():
    db = _FakeDB({(10, 5): ProjectRole.editor})
    user = _user(uid=10)
    assert asyncio.run(deps.get_project_role(db, user, project_id=5)) == ProjectRole.editor


def test_get_project_role_returns_none_when_not_member():
    db = _FakeDB({(10, 5): ProjectRole.editor})
    user = _user(uid=10)
    assert asyncio.run(deps.get_project_role(db, user, project_id=999)) is None


def test_require_project_access_passes_for_admin():
    db = _FakeDB()
    admin = _user(role=UserRole.admin, uid=1)
    checker = deps.require_project_access(ProjectRole.owner)
    result = asyncio.run(checker(project_id=99, current_user=admin, db=db))
    assert result is admin
    assert db.audit_records == []


def test_require_project_access_passes_when_role_sufficient():
    db = _FakeDB({(10, 5): ProjectRole.editor})
    user = _user(uid=10)
    checker = deps.require_project_access(ProjectRole.editor)
    result = asyncio.run(checker(project_id=5, current_user=user, db=db))
    assert result is user
    assert db.audit_records == []


def test_require_project_access_denies_lower_role_and_writes_audit():
    db = _FakeDB({(10, 5): ProjectRole.viewer})
    user = _user(uid=10)
    checker = deps.require_project_access(ProjectRole.editor)
    raised = False
    try:
        asyncio.run(checker(project_id=5, current_user=user, db=db))
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 403
    assert raised
    assert len(db.audit_records) == 1
    record = db.audit_records[0]
    assert record["action"] == "access_denied"
    assert record["project_id"] == 5
    assert record["user_id"] == 10
    assert "min_role=editor" in record["detail"]


def test_require_project_access_denies_non_member():
    db = _FakeDB()  # 无任何成员关系
    user = _user(uid=10)
    checker = deps.require_project_access(ProjectRole.viewer)
    raised = False
    try:
        asyncio.run(checker(project_id=5, current_user=user, db=db))
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 403
    assert raised
    assert db.audit_records[0]["detail"].endswith("actual=none")


def test_assert_project_access_works_outside_path_param():
    db = _FakeDB({(10, 5): ProjectRole.owner})
    user = _user(uid=10)
    asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=ProjectRole.editor))
    assert db.audit_records == []


def test_assert_project_access_denies_and_writes_audit():
    db = _FakeDB()
    user = _user(uid=10)
    raised = False
    try:
        asyncio.run(deps.assert_project_access(db, user, project_id=5, min_role=ProjectRole.viewer))
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 403
    assert raised
    assert len(db.audit_records) == 1
