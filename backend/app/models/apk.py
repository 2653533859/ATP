from sqlalchemy import String, Text, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Apk(Base, TimestampMixin):
    __tablename__ = "apks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(256))
    version_name: Mapped[str | None] = mapped_column(String(64))
    version_code: Mapped[int | None] = mapped_column(Integer)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)  # MinIO path
    description: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    project: Mapped["Project"] = relationship()  # noqa: F821
