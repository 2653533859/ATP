from types import SimpleNamespace

from sqlalchemy import select

from app.models import load_all_models
from app.models.apk import Apk
from app.models.user import UserRole
from app.services.project_scope import scope_to_visible_projects

load_all_models()


def test_non_admin_project_scope_uses_membership_subquery():
    user = SimpleNamespace(id=7, role=UserRole.viewer)

    sql = str(scope_to_visible_projects(select(Apk), Apk.project_id, user))

    assert "user_projects" in sql
    assert "user_projects.user_id" in sql


def test_explicit_project_remains_constrained_by_membership():
    user = SimpleNamespace(id=7, role=UserRole.engineer)

    sql = str(scope_to_visible_projects(select(Apk), Apk.project_id, user, project_id=9))

    assert "user_projects" in sql
    assert "apks.project_id =" in sql


def test_admin_project_scope_uses_all_projects():
    user = SimpleNamespace(id=1, role=UserRole.admin)

    sql = str(scope_to_visible_projects(select(Apk), Apk.project_id, user))

    assert "FROM projects" in sql
    assert "user_projects" not in sql
