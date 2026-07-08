"""P3.C 跨项目越权 + 项目成员管理 + 审计查询 API 单测。"""

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
    "jwt",
    types.SimpleNamespace(
        InvalidTokenError=type("InvalidTokenError", (Exception,), {}),
        encode=lambda *a, **kw: "",
        decode=lambda *a, **kw: {},
    ),
)
sys.modules.setdefault("passlib", types.SimpleNamespace())
sys.modules.setdefault(
    "passlib.context",
    types.SimpleNamespace(
        CryptContext=lambda *a, **kw: types.SimpleNamespace(hash=lambda x: x, verify=lambda *a, **kw: True)
    ),
)

# 强制清掉其他 api 测试的 stub，导入真实 deps
sys.modules.pop("app.api.deps", None)
sys.modules.pop("app.api.v1.projects", None)
sys.modules.pop("app.api.v1.statistics", None)


# 给 statistics stub invalidate_stats_cache
async def _noop():
    return None


sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(invalidate_stats_cache=_noop)

from fastapi import HTTPException

from app.api import deps
from app.api.v1 import projects as projects_api
from app.models.bootstrap import load_all_models
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject

load_all_models()


def _user(role=UserRole.engineer, uid=10) -> User:
    return User(id=uid, username=f"u{uid}", email=f"u{uid}@x", hashed_password="x", role=role, is_active=True)


class _FakeDB:
    """通用 mock：存储 (cls_name, pk) → obj；execute 解析 select.where 条件。"""

    def __init__(self):
        self.store: dict[tuple[str, int], object] = {}
        self.user_projects: dict[tuple[int, int], ProjectRole] = {}
        self.audit_records: list = []
        self.added: list = []
        self.deleted: list = []
        self.commits = 0
        self._next_id = 100

    async def get(self, cls, pk):
        return self.store.get((cls.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.store[(obj.__class__.__name__, obj.id)] = obj
        self.added.append(obj)
        # 捕获 UserProject 与 AuditLog
        if obj.__class__.__name__ == "UserProject":
            self.user_projects[(obj.user_id, obj.project_id)] = obj.role
        if obj.__class__.__name__ == "AuditLog":
            self.audit_records.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        return None

    async def refresh(self, _obj):
        return None

    async def delete(self, obj):
        self.deleted.append(obj)
        self.store.pop((obj.__class__.__name__, obj.id), None)
        if obj.__class__.__name__ == "UserProject":
            self.user_projects.pop((obj.user_id, obj.project_id), None)

    async def execute(self, stmt):
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled).lower()
        # select(UserProject.role) where user_id=X, project_id=Y
        if "user_projects.role" in sql or "select user_projects" in sql:
            import re

            uid_m = re.search(r"user_projects\.user_id\s*=\s*(\d+)", sql)
            pid_m = re.search(r"user_projects\.project_id\s*=\s*(\d+)", sql)
            role_only = ("user_projects.role" in sql and "user_projects.id" not in sql) or (
                "select user_projects.role" in sql
            )
            if uid_m and pid_m:
                role = self.user_projects.get((int(uid_m.group(1)), int(pid_m.group(1))))

                class _R:
                    def scalar_one_or_none(_self):
                        return role

                    def scalar_one(_self):
                        return role

                return _R()

        class _R2:
            def scalars(_self):
                return types.SimpleNamespace(all=lambda: [])

            def scalar_one_or_none(_self):
                return None

            def scalar_one(_self):
                return 0

            def all(_self):
                return []

        return _R2()


def test_create_project_assigns_creator_as_owner():
    db = _FakeDB()
    user = _user(role=UserRole.engineer, uid=10)
    body = types.SimpleNamespace(model_dump=lambda: {"name": "P1", "project_code": None}, name="P1")

    result = asyncio.run(projects_api.create_project(body=body, db=db, current_user=user))

    # project + UserProject 都被 add
    assert any(o.__class__.__name__ == "Project" for o in db.added)
    user_proj = next(o for o in db.added if o.__class__.__name__ == "UserProject")
    assert user_proj.user_id == 10
    assert user_proj.role == ProjectRole.owner


def test_get_project_denies_non_member():
    db = _FakeDB()
    from app.models.project import Project

    db.store[("Project", 99)] = Project(id=99, name="X", project_code="X", owner_id=1)
    user = _user(uid=10)

    # 通过 dependency 注入：模拟 FastAPI 行为，require_project_access 应抛 403
    checker = deps.require_project_access(ProjectRole.viewer)
    raised = False
    try:
        asyncio.run(checker(project_id=99, current_user=user, db=db))
    except HTTPException as exc:
        raised = exc.status_code == 403
    assert raised
    # 审计写入
    assert any(getattr(a, "action", None) == "access_denied" for a in db.audit_records)


def test_get_project_allows_member():
    db = _FakeDB()
    from app.models.project import Project

    db.store[("Project", 99)] = Project(id=99, name="X", project_code="X", owner_id=1)
    user = _user(uid=10)
    db.user_projects[(10, 99)] = ProjectRole.viewer

    checker = deps.require_project_access(ProjectRole.viewer)
    result = asyncio.run(checker(project_id=99, current_user=user, db=db))
    assert result is user
    assert db.audit_records == []


def test_owner_role_satisfies_editor_min():
    db = _FakeDB()
    user = _user(uid=10)
    db.user_projects[(10, 99)] = ProjectRole.owner

    checker = deps.require_project_access(ProjectRole.editor)
    result = asyncio.run(checker(project_id=99, current_user=user, db=db))
    assert result is user
