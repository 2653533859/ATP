"""Bootstrap and preserve the single-user, single-project local workspace."""

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject


async def ensure_local_workspace() -> int:
    if not settings.ATP_LOCAL_MODE:
        raise RuntimeError("local workspace bootstrap requires Windows local mode")

    async with AsyncSessionLocal() as db:
        user_count = await db.scalar(select(func.count(User.id)))
        if user_count != 1:
            raise RuntimeError(
                "local profile requires exactly one user; preserve data and resolve extra users manually"
            )
        admin = await db.scalar(select(User))
        if admin is None or admin.role != UserRole.admin or not admin.is_active:
            raise RuntimeError("local profile requires one active administrator")

        projects = list((await db.scalars(select(Project).order_by(Project.id))).all())
        if len(projects) > 1:
            raise RuntimeError("local profile requires one project; preserve data and resolve extra projects manually")
        if projects:
            project = projects[0]
            if project.owner_id != admin.id:
                raise RuntimeError("local project owner differs from the local administrator")
        else:
            project = Project(name="本地项目", project_code="LOCAL", owner_id=admin.id, status="active")
            db.add(project)
            await db.flush()

        membership = await db.scalar(
            select(UserProject).where(UserProject.user_id == admin.id, UserProject.project_id == project.id)
        )
        if membership is None:
            db.add(UserProject(user_id=admin.id, project_id=project.id, role=ProjectRole.owner))

        module_id = await db.scalar(select(Module.id).where(Module.project_id == project.id).limit(1))
        if module_id is None:
            db.add(Module(name="默认模块", module_code="DEFAULT", project_id=project.id, sort_order=0))
        await db.commit()
        return project.id
