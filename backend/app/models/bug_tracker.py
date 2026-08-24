import enum
from sqlalchemy import String, Text, ForeignKey, JSON, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class TrackerType(str, enum.Enum):
    jira = "jira"
    zentao = "zentao"
    github = "github"
    gitlab = "gitlab"


class BugTracker(Base, TimestampMixin):
    __tablename__ = "bug_trackers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    tracker_type: Mapped[TrackerType] = mapped_column(Enum(TrackerType), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 配置 JSON，结构因类型而异：
    # jira:   {"base_url": "https://xxx.atlassian.net", "email": "...", "api_token": "...", "project_key": "ATP"}
    # zentao: {"base_url": "http://zentao.xxx.com", "account": "...", "password": "...", "product_id": 1,
    #          "product_map": {"backend": 1, "frontend": 2}}   # 多产品支持，product_id 为默认
    # github: {"base_url": "https://api.github.com", "owner": "foo", "repo": "bar", "token": "..."}
    # gitlab: {"base_url": "https://gitlab.com", "project_id": "group/project", "token": "..."}
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    field_mapping: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="bug_trackers")  # noqa: F821
    external_links: Mapped[list["DefectExternalLink"]] = relationship(  # noqa: F821
        back_populates="tracker",
        cascade="all, delete-orphan",
    )
