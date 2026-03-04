from pydantic import BaseModel, Field, model_validator
from datetime import datetime


# -- Environment --
class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    project_id: int


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = None


class EnvironmentOut(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# -- EnvVariable --
class EnvVariableItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=128, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    value: str = ""
    is_secret: bool = False


class EnvVariableOut(BaseModel):
    id: int
    key: str
    value: str
    is_secret: bool

    model_config = {"from_attributes": True}


class EnvVariableBatchSave(BaseModel):
    variables: list[EnvVariableItem] = Field(default=[], max_length=200)

    @model_validator(mode="after")
    def check_unique_keys(self):
        keys = [v.key for v in self.variables]
        if len(keys) != len(set(keys)):
            raise ValueError("变量名不能重复")
        return self
