"""企业资源模型（api-contract §3/§5）。"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CompanyOut(ORMModel):
    id: uuid.UUID
    canonical_name: str
    normalized_name: str
    aliases: list[Any]
    industry: str | None
    phone: str | None
    website: str | None
    merged_into_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ContactOut(ORMModel):
    id: uuid.UUID
    company_id: uuid.UUID | None
    name: str | None
    phone: str | None
    email: str | None
    wechat_id: str | None
    created_at: datetime
    updated_at: datetime


class CompanyListItem(ORMModel):
    id: uuid.UUID
    canonical_name: str
    normalized_name: str
    aliases: list[Any]
    industry: str | None
    phone: str | None
    website: str | None
    created_at: datetime
    updated_at: datetime
    lead_count: int
    recent_inquiry_at: datetime | None


class CompanyCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    industry: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=255)


class CompanyUpdate(BaseModel):
    canonical_name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = None
    industry: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=255)


class CompanyMergeRequest(BaseModel):
    source_company_id: uuid.UUID
    target_company_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=255)


class ContactCreate(BaseModel):
    company_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    wechat_id: str | None = Field(default=None, max_length=128)


class ContactUpdate(BaseModel):
    company_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    wechat_id: str | None = Field(default=None, max_length=128)
