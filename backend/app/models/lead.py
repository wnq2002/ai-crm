"""线索表（PRD §7 / architecture §5）。"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

# 状态机枚举（ADR-021：三维正交）
QUALIFICATION_PENDING = "pending"
QUALIFICATION_VALID = "valid"
QUALIFICATION_INVALID = "invalid"
HANDOFF_NOT_HANDED_OFF = "not_handed_off"
HANDOFF_HANDED_OFF = "handed_off"
OUTCOME_UNKNOWN = "unknown"
OUTCOME_IN_PROGRESS = "in_progress"
OUTCOME_WON = "won"
OUTCOME_LOST = "lost"
OUTCOME_DEFERRED = "deferred"
INTAKE_MANUAL = "manual"
INTAKE_IMPORT = "import"
INTAKE_API = "api"


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        Index(
            "uq_leads_external_event",
            "source_category_id",
            "external_source_event_id",
            unique=True,
            postgresql_where=text("external_source_event_id IS NOT NULL"),
        ),
    )

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    company_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_name_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wechat_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    need_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_need_types.id"), nullable=True, index=True
    )
    inquiry_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_source_categories.id"),
        nullable=False,
        index=True,
    )
    source_detail_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_source_details.id"), nullable=True
    )
    source_detail_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    intake_method: Mapped[str] = mapped_column(String(16), nullable=False)
    external_source_event_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    source_payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    qualification_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=QUALIFICATION_PENDING, index=True
    )
    handoff_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=HANDOFF_NOT_HANDED_OFF, index=True
    )
    outcome_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OUTCOME_UNKNOWN, index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True
    )
    department_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("department_contacts.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
