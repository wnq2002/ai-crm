"""跟进活动表（PRD §7 / architecture §5）。"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

ACTIVITY_KIND_PHONE = "phone"
ACTIVITY_KIND_WECHAT_REQUEST = "wechat_request"
ACTIVITY_KIND_WECHAT_APPROVED = "wechat_approved"
ACTIVITY_KIND_WECHAT_CHAT = "wechat_chat"
ACTIVITY_KIND_NOTE = "note"

WECHAT_KINDS = (
    ACTIVITY_KIND_WECHAT_REQUEST,
    ACTIVITY_KIND_WECHAT_APPROVED,
    ACTIVITY_KIND_WECHAT_CHAT,
)


class LeadActivity(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "lead_activities"
    __table_args__ = (
        UniqueConstraint(
            "created_by", "idempotency_key", name="uq_activity_idempotency"
        ),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    revoke_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
