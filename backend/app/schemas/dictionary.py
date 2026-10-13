"""配置字典资源模型（api-contract §3/§10）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DepartmentOut(ORMModel):
    id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class DepartmentContactOut(ORMModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    is_default: bool
    active: bool
    created_at: datetime


class SourceCategoryOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    active: bool
    created_at: datetime


class SourceDetailOut(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class NeedTypeOut(ORMModel):
    id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


class DepartmentContactCreate(BaseModel):
    department_id: uuid.UUID
    name: str = Field(min_length=1, max_length=128)
    is_default: bool = False
    active: bool = True


class DepartmentContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_default: bool | None = None
    active: bool | None = None


class SourceCategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)


class SourceCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


class SourceDetailCreate(BaseModel):
    category_id: uuid.UUID
    name: str = Field(min_length=1, max_length=128)


class SourceDetailUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


class NeedTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class NeedTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None
