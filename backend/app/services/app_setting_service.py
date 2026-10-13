"""app_settings 键值配置服务（AI Provider 等，ADR-029）。

密钥（api_key）仅写入不读回：读取/审计一律脱敏，日志不落明文。
存储约定见 `docs/decisions.md`「ADR-029 实现细节」。
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.user import User
from app.schemas.setting import AIConfigIn, AIConfigOut
from app.services import audit_service

AI_PROVIDER_KEY = "ai_provider"
_MASKED_KEY = "***configured***"


def _mask(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """审计用脱敏副本：api_key 只保留「是否已配置」标记，绝不落明文。"""
    if value is None:
        return None
    masked = dict(value)
    masked["api_key"] = _MASKED_KEY if masked.get("api_key") else None
    return masked


def get_ai_config(db: Session) -> AIConfigOut:
    row = db.scalar(select(AppSetting).where(AppSetting.key == AI_PROVIDER_KEY))
    if row is None:
        return AIConfigOut()
    value = row.value or {}
    configured = bool(value.get("api_key"))
    return AIConfigOut(
        provider=value.get("provider"),
        endpoint=value.get("endpoint"),
        model=value.get("model"),
        timeout_seconds=value.get("timeout_seconds") or 30,
        api_key_configured=configured,
        api_key=_MASKED_KEY if configured else None,
        updated_at=row.updated_at,
    )


def save_ai_config(db: Session, actor: User, payload: AIConfigIn) -> AIConfigOut:
    row = db.scalar(select(AppSetting).where(AppSetting.key == AI_PROVIDER_KEY))
    before = dict(row.value) if row is not None and row.value else None

    value: dict[str, Any] = {
        "provider": payload.provider,
        "endpoint": str(payload.endpoint),
        "model": payload.model,
        "timeout_seconds": payload.timeout_seconds,
    }
    if payload.api_key is None:
        existing_key = (row.value or {}).get("api_key") if row is not None else None
        if existing_key:
            value["api_key"] = existing_key
    elif payload.api_key != "":
        value["api_key"] = payload.api_key
    # 空字符串 → 清除密钥（不写入 api_key 键）

    now = datetime.now(timezone.utc)
    if row is None:
        row = AppSetting(
            key=AI_PROVIDER_KEY, value=value, updated_by=actor.id, updated_at=now
        )
        db.add(row)
    else:
        row.value = value
        row.updated_by = actor.id
        row.updated_at = now

    audit_service.record(
        db,
        actor_id=actor.id,
        action="settings.ai_update",
        resource_type="app_setting",
        resource_id=AI_PROVIDER_KEY,
        before=_mask(before),
        after=_mask(value),
    )
    db.commit()

    configured = bool(value.get("api_key"))
    return AIConfigOut(
        provider=value["provider"],
        endpoint=value["endpoint"],
        model=value["model"],
        timeout_seconds=value["timeout_seconds"],
        api_key_configured=configured,
        api_key=_MASKED_KEY if configured else None,
        updated_at=row.updated_at,
    )