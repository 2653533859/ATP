"""Project visibility filters shared by authenticated resource queries."""

from sqlalchemy import select
from sqlalchemy.sql import Select

from app.models.project import Project
from app.models.user import User, UserRole
from app.models.user_project import UserProject


def visible_project_ids(user: User) -> Select:
    if getattr(user, "role", None) == UserRole.admin:
        return select(Project.id)
    return select(UserProject.project_id).where(UserProject.user_id == getattr(user, "id", 0))


def scope_to_visible_projects(stmt: Select, project_column, user: User, project_id: int | None = None) -> Select:
    scoped = stmt.where(project_column.in_(visible_project_ids(user)))
    if project_id is not None:
        return scoped.where(project_column == project_id)
    return scoped
