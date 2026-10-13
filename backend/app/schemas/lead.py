"""线索资源模型（api-contract §3/§4）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.company import CompanyOut


class LeadOut(ORMModel):
    id: uuid.UUID
    company_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    company_name_raw: str | None
    contact_name_raw: str | None
    phone_raw: str | None
    email_raw: str | None
    wechat_raw: str | None
    need_type_id: uuid.UUID | None
    inquiry_text: str | None
    notes: str | None
    occurred_at: datetime
    source_category_id: uuid.UUID
    source_detail_id: uuid.UUID | None
    source_detail_text: str | None
    intake_method: str
    external_source_event_id: str | None
    qualification_status: str
    handoff_status: str
    outcome_status: str
    department_id: uuid.UUID | None
    department_contact_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    version: int
    phone_total_count: int = 0
    wechat_count: int = 0
    recent_followup_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    follow_up_status: str = "normal"
    wechat_relationship: str = "none"


class LeadListItem(ORMModel):
    id: uuid.UUID
    occurred_at: datetime
    company_name_raw: str | None
    contact_name_raw: str | None
    contact_summary: str | None
    need_type_id: uuid.UUID | None
    inquiry_text: str | None
    qualification_status: str
    handoff_status: str
    outcome_status: str
    department_id: uuid.UUID | None
    department_contact_id: uuid.UUID | None
    source_category_id: uuid.UUID
    source_detail_id: uuid.UUID | None
    source_detail_text: str | None
    recent_followup_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    follow_up_count: int = 0
    follow_up_status: str = "normal"
    created_at: datetime
    updated_at: datetime


class LeadParseRecordCreate(BaseModel):
    """创建线索时随附的 AI 解析记录（原文必保留，解析结果可选）。"""

    raw_text: str = Field(min_length=1)
    parsed_json: dict | None = None


class LeadCreate(BaseModel):
    occurred_at: datetime | None = None
    contact_name_raw: str | None = Field(default=None, max_length=128)
    phone_raw: str | None = Field(default=None, max_length=64)
    email_raw: str | None = Field(default=None, max_length=255)
    wechat_raw: str | None = Field(default=None, max_length=128)
    company_name_raw: str | None = Field(default=None, max_length=200)
    need_type_id: uuid.UUID | None = None
    inquiry_text: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    source_category_id: uuid.UUID | None = None
    source_detail_id: uuid.UUID | None = None
    source_detail_text: str | None = Field(default=None, max_length=255)
    intake_method: str = Field(default="manual", pattern=r"^(manual|import|api)$")
    external_source_event_id: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=128)
    parse_record: LeadParseRecordCreate | None = None


class LeadUpdate(BaseModel):
    version: int | None = Field(default=None, ge=1)
    occurred_at: datetime | None = None
    contact_name_raw: str | None = Field(default=None, max_length=128)
    phone_raw: str | None = Field(default=None, max_length=64)
    email_raw: str | None = Field(default=None, max_length=255)
    wechat_raw: str | None = Field(default=None, max_length=128)
    company_name_raw: str | None = Field(default=None, max_length=200)
    need_type_id: uuid.UUID | None = None
    inquiry_text: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    source_category_id: uuid.UUID | None = None
    source_detail_id: uuid.UUID | None = None
    source_detail_text: str | None = Field(default=None, max_length=255)


class LinkCompanyRequest(BaseModel):
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None


class LeadCreateResponse(BaseModel):
    lead: LeadOut
    company_candidates: list[CompanyOut]
    duplicate_hints: list[str] = Field(default_factory=list)


class FieldExtraction(BaseModel):
    value: str | None = None
    confidence: str | None = None


class LeadParseRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=20000)


class LeadParseResponse(BaseModel):
    company_name: FieldExtraction = Field(default_factory=FieldExtraction)
    contact_name: FieldExtraction = Field(default_factory=FieldExtraction)
    phone: FieldExtraction = Field(default_factory=FieldExtraction)
    email: FieldExtraction = Field(default_factory=FieldExtraction)
    inquiry_text: FieldExtraction = Field(default_factory=FieldExtraction)
    need_type: FieldExtraction = Field(default_factory=FieldExtraction)
    source_channel: FieldExtraction = Field(default_factory=FieldExtraction)
    hints: list[str] = Field(default_factory=list)


class DuplicateCheckRequest(BaseModel):
    phone_raw: str | None = Field(default=None, max_length=64)
    email_raw: str | None = Field(default=None, max_length=255)
    company_name_raw: str | None = Field(default=None, max_length=200)
    external_source_event_id: str | None = Field(default=None, max_length=255)
    source_category_id: uuid.UUID | None = None


class DuplicateCheckResponse(BaseModel):
    contact_duplicate: bool = False
    contact_hint: str | None = None
    company_candidates: list[CompanyOut] = Field(default_factory=list)
    external_event_conflict: bool = False


class LeadEventOut(ORMModel):
    id: uuid.UUID
    event_type: str
    before_json: dict | None
    after_json: dict | None
    created_by: uuid.UUID
    created_at: datetime
