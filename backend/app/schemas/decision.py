"""判断/交接/反馈请求模型（api-contract §7）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QualificationRequest(BaseModel):
    qualification_status: str = Field(pattern=r"^(pending|valid|invalid)$")
    reason: str | None = Field(default=None, max_length=255)


class HandoffRequest(BaseModel):
    department_id: uuid.UUID
    department_contact_id: uuid.UUID | None = None
    note: str | None = None
    reason: str | None = Field(default=None, max_length=255)


class OutcomeRequest(BaseModel):
    outcome_status: str = Field(pattern=r"^(unknown|in_progress|won|lost|deferred)$")
    note: str | None = None
    feedback_at: datetime | None = None
