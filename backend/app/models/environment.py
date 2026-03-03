from sqlalchemy import String, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Environment(Base, TimestampMixin):
    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)

    variables: Mapped[list["EnvVariable"]] = relationship(
        back_populates="environment", cascade="all, delete-orphan"
    )


class EnvVariable(Base, TimestampMixin):
    __tablename__ = "env_variables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    env_id: Mapped[int] = mapped_column(ForeignKey("environments.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    is_secret: Mapped[bool] = mapped_column(default=False)  # 敏感值在响应中脱敏

    environment: Mapped["Environment"] = relationship(back_populates="variables")
