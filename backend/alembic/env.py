"""Alembic 环境配置"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.models.base import Base

# 导入所有模型以确保 metadata 包含全部表
from app.models.user import User  # noqa
from app.models.project import Project, Module  # noqa
from app.models.case import TestCase, CaseStep, TestRun, StepResult, CaseSnapshot  # noqa
from app.models.bug_tracker import BugTracker  # noqa
from app.models.environment import Environment, EnvVariable  # noqa
from app.models.suite import TestSuite, SuiteRun  # noqa
from app.models.plan import TestPlan, PlanRun  # noqa
from app.models.notification import NotificationConfig  # noqa
from app.models.ios import IosApp, IosDevice, IosDeviceLease  # noqa
from app.models.dataset import TestDataset, TestDatasetVersion  # noqa
from app.models.defect import Defect, DefectRunLink  # noqa
from app.models.defect_external import DefectExternalLink  # noqa

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 使用同步 URL（alembic 不支持 asyncpg）
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=sync_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
