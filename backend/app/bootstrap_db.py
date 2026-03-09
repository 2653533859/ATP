from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import sync_engine
from app.models.base import Base
from app.models.bootstrap import load_all_models

load_all_models()


def main() -> None:
    # 当前项目仍依赖模型直建表兜底，fresh DB 启动时先确保完整 schema 存在。
    Base.metadata.create_all(sync_engine)

    with sync_engine.connect() as conn:
        inspector = inspect(conn)
        if "alembic_version" not in inspector.get_table_names():
            cfg = Config("alembic.ini")
            command.stamp(cfg, "head")


if __name__ == "__main__":
    main()
