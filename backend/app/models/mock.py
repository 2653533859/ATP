import enum
from sqlalchemy import String, Text, ForeignKey, JSON, Enum, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class MockMethod(str, enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    ANY = "ANY"


class MockRule(Base, TimestampMixin):
    __tablename__ = "mock_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    method: Mapped[MockMethod] = mapped_column(Enum(MockMethod), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    response_body: Mapped[str | None] = mapped_column(Text)
    match_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    delay_ms: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    render_template: Mapped[bool] = mapped_column(Boolean, default=False)
    record_requests: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    recorded_samples: Mapped[list] = mapped_column(JSON, default=list)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    project: Mapped["Project"] = relationship()  # noqa: F821
