"""用户资源模型（api-contract §3）。"""

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: str
    is_active: bool
    must_change_password: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern=r"^(admin|market)$")
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = Field(default=None, pattern=r"^(admin|market)$")
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
