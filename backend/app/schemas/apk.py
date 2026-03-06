from pydantic import BaseModel
from datetime import datetime


class ApkOut(BaseModel):
    id: int
    project_id: int
    filename: str
    package_name: str | None
    version_name: str | None
    version_code: int | None
    file_size: int
    object_name: str
    description: str | None
    uploaded_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApkUpdate(BaseModel):
    description: str | None = None
    package_name: str | None = None
    version_name: str | None = None
    version_code: int | None = None
