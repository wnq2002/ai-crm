"""跟进活动模型（api-contract §6）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ActivityCreate(BaseModel):
    kind: str = Field(pattern=r"^(phone|wechat_request|wechat_approved|wechat_chat|note)$")
    result: str | None = Field(
        default=None, pattern=r"^(connected|unconnected|rejected)$"
    )
    content: str | None = Field(default=None, max_length=2000)
    happened_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)


class ActivityOut(ORMModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    kind: str
    result: str | None
    content: str | None
    happened_at: datetime
    created_at: datetime
    created_by: uuid.UUID
    revoked_at: datetime | None
    revoke_reason: str | None


class RevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class ActivityReviseRequest(BaseModel):
    """事件修正（V1.4）：修正发生时间/结果/内容，reason 必填，写修正历史。"""

    reason: str = Field(min_length=1, max_length=255)
    happened_at: datetime | None = None
    result: str | None = Field(
        default=None, pattern=r"^(connected|unconnected|rejected)$"
    )
    content: str | None = Field(default=None, max_length=2000)
