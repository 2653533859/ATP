from pydantic import BaseModel, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthSessionResponse(BaseModel):
    """登录状态响应；令牌通过 HttpOnly Cookie 下发，不回显给浏览器脚本。"""

    authenticated: bool
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    username: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, min_length=3, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_change_target(self) -> "UserProfileUpdate":
        if self.username is None and self.email is None and self.new_password is None:
            raise ValueError("至少填写一项需要修改的账号信息")
        if self.username is not None:
            self.username = self.username.strip()
            if not self.username:
                raise ValueError("用户名不能为空")
        return self

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise ValueError("邮箱格式无效")
        return value.strip() if value is not None else None


class UserLookupOut(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}


class UserAdminCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="tester", pattern="^(admin|engineer|tester|viewer)$")
    is_active: bool = True

    @model_validator(mode="after")
    def normalize_username(self) -> "UserAdminCreate":
        self.username = self.username.strip()
        if not self.username:
            raise ValueError("用户名不能为空")
        return self

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("邮箱格式无效")
        return value


class UserAdminUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, min_length=3, max_length=128)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|engineer|tester|viewer)$")
    is_active: bool | None = None

    @model_validator(mode="after")
    def normalize_username(self) -> "UserAdminUpdate":
        if self.username is not None:
            self.username = self.username.strip()
            if not self.username:
                raise ValueError("用户名不能为空")
        if (
            self.username is None
            and self.email is None
            and self.password is None
            and self.role is None
            and self.is_active is None
        ):
            raise ValueError("至少填写一项需要修改的信息")
        return self

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if "@" not in value or value.startswith("@") or value.endswith("@"):
                raise ValueError("邮箱格式无效")
        return value
