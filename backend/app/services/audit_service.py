"""审计服务（PRD §13 / architecture §11）。

仅记录非敏感字段；严禁写入密码、完整邮箱/手机号、API Key。
"""

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.request_id import current_request_id
from app.models.audit_log import AuditLog


def _dump(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, default=str)


def record(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_json=_dump(before),
            after_json=_dump(after),
            request_id=current_request_id() or None,
        )
    )
