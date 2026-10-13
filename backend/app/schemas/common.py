"""通用 schema：ORM 基类、分页、错误。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict | None = None
