"""跟进活动业务逻辑（PRD §5.3/§5.4，api-contract §6，V1.4 三态微信 + 事件修正）。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError, conflict, forbidden, not_found
from app.models.lead_activity import (
    ACTIVITY_KIND_NOTE,
    ACTIVITY_KIND_PHONE,
    ACTIVITY_KIND_WECHAT_CHAT,
    ACTIVITY_KIND_WECHAT_REQUEST,
    WECHAT_KINDS,
    LeadActivity,
)
from app.models.lead_event_revision import LeadEventRevision
from app.models.user import ROLE_ADMIN, User
from app.repositories import lead_activity_repository, lead_repository
from app.schemas.activity import ActivityCreate, ActivityReviseRequest
from app.services import audit_service

WECHAT_RELATIONSHIP_NONE = "none"
WECHAT_RELATIONSHIP_PENDING = "pending"
WECHAT_RELATIONSHIP_APPROVED = "approved"


def get_wechat_relationship(db: Session, lead_id: uuid.UUID) -> str:
    """微信关系由事件实时派生（ADR-028）：最新一条有效微信事件决定。

    - 无微信事件 → none
    - 最新为 wechat_request（发送好友申请）→ pending
    - 最新为 wechat_approved / wechat_chat → approved（沟通仅在已通过后发生）
    """
    latest = db.scalar(
        select(LeadActivity)
        .where(
            LeadActivity.lead_id == lead_id,
            LeadActivity.kind.in_(WECHAT_KINDS),
            LeadActivity.revoked_at.is_(None),
        )
        .order_by(LeadActivity.happened_at.desc(), LeadActivity.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return WECHAT_RELATIONSHIP_NONE
    if latest.kind == ACTIVITY_KIND_WECHAT_REQUEST:
        return WECHAT_RELATIONSHIP_PENDING
    return WECHAT_RELATIONSHIP_APPROVED


def create_activity(
    db: Session, actor: User, lead_id: uuid.UUID, payload: ActivityCreate
) -> LeadActivity:
    lead = lead_repository.get_lead_by_id(db, lead_id)
    if lead is None or lead.archived_at is not None:
        raise not_found("线索不存在")

    if payload.kind == ACTIVITY_KIND_PHONE:
        if payload.result not in ("connected", "unconnected", "rejected"):
            raise APIError(
                422, "VALIDATION_ERROR", "电话跟进 result 必须为 connected/unconnected/rejected"
            )
    elif payload.result is not None:
        raise APIError(422, "VALIDATION_ERROR", "微信/备注不能写联系结果")

    if payload.kind == ACTIVITY_KIND_WECHAT_CHAT:
        if get_wechat_relationship(db, lead_id) != WECHAT_RELATIONSHIP_APPROVED:
            raise APIError(
                422, "VALIDATION_ERROR", "仅微信关系已通过时才可记录微信沟通"
            )

    if payload.idempotency_key:
        existing = lead_activity_repository.get_activity_by_idempotency(
            db, actor.id, payload.idempotency_key
        )
        if existing is not None:
            return existing

    happened_at = payload.happened_at or datetime.now(timezone.utc)
    if happened_at > datetime.now(timezone.utc):
        raise APIError(422, "VALIDATION_ERROR", "跟进时间不能晚于当前时间")

    activity = LeadActivity(
        lead_id=lead_id,
        kind=payload.kind,
        result=payload.result if payload.kind == ACTIVITY_KIND_PHONE else None,
        content=payload.content,
        happened_at=happened_at,
        created_by=actor.id,
        idempotency_key=payload.idempotency_key,
    )
    lead_activity_repository.create_activity(db, activity)
    # 记录沟通后更新「下次跟进时间」：传值则设为该值，未传则清空（本次任务完成）。
    # 备注不算沟通，不改变下次跟进时间。
    if payload.kind != ACTIVITY_KIND_NOTE:
        lead.next_follow_up_at = payload.next_follow_up_at
    db.commit()
    return activity


def list_activities(db: Session, lead_id: uuid.UUID) -> list[LeadActivity]:
    return lead_activity_repository.list_activities(db, lead_id)


def get_followup_summary(db: Session, lead_id: uuid.UUID) -> dict:
    """服务端计算跟进聚合口径（仅有效事件，撤销不计入）。"""
    activities = lead_activity_repository.list_activities(db, lead_id)
    phone_total = sum(1 for a in activities if a.kind == ACTIVITY_KIND_PHONE)
    wechat_count = sum(1 for a in activities if a.kind in WECHAT_KINDS)
    recent_followup = max((a.happened_at for a in activities), default=None)
    return {
        "phone_total_count": phone_total,
        "wechat_count": wechat_count,
        "recent_followup_at": recent_followup,
    }


def _activity_snapshot(activity: LeadActivity) -> dict:
    return {
        "happened_at": activity.happened_at.isoformat(),
        "result": activity.result,
        "content": activity.content,
    }


def revise_activity(
    db: Session, actor: User, activity_id: uuid.UUID, payload: ActivityReviseRequest
) -> LeadActivity:
    """修正事件发生时间/结果/内容，写 `lead_event_revisions` 留痕；created_at 不可改。"""
    activity = lead_activity_repository.get_activity_by_id(db, activity_id)
    if activity is None:
        raise not_found("跟进记录不存在")
    if activity.revoked_at is not None:
        raise conflict("已撤销的记录不可修正")

    if actor.role != ROLE_ADMIN and actor.id != activity.created_by:
        raise forbidden("无权限修正该记录")

    changed: dict[str, object] = {}
    if payload.happened_at is not None:
        if payload.happened_at > datetime.now(timezone.utc):
            raise APIError(422, "VALIDATION_ERROR", "修正后的发生时间不能晚于当前时间")
        if payload.happened_at != activity.happened_at:
            changed["happened_at"] = payload.happened_at
    if payload.result is not None:
        if activity.kind != ACTIVITY_KIND_PHONE:
            raise APIError(422, "VALIDATION_ERROR", "非电话事件不能设置联系结果")
        if payload.result != activity.result:
            changed["result"] = payload.result
    if payload.content is not None:
        if payload.content != activity.content:
            changed["content"] = payload.content

    if not changed:
        raise APIError(422, "VALIDATION_ERROR", "至少提供一项修正内容")

    before_json = _activity_snapshot(activity)
    for field, value in changed.items():
        setattr(activity, field, value)
    after_json = _activity_snapshot(activity)

    db.add(
        LeadEventRevision(
            activity_id=activity.id,
            before_json=before_json,
            after_json=after_json,
            reason=payload.reason,
            revised_by=actor.id,
        )
    )
    audit_service.record(
        db,
        actor_id=actor.id,
        action="activity.revise",
        resource_type="lead_activity",
        resource_id=str(activity.id),
        after={"reason": payload.reason},
    )
    db.commit()
    return activity


def revoke_activity(
    db: Session, actor: User, activity_id: uuid.UUID, reason: str
) -> LeadActivity:
    activity = lead_activity_repository.get_activity_by_id(db, activity_id)
    if activity is None:
        raise not_found("跟进记录不存在")

    # 创建者本人或 admin 可撤销
    if actor.role != ROLE_ADMIN and actor.id != activity.created_by:
        raise forbidden("无权限撤销该记录")

    if activity.revoked_at is not None:
        return activity

    activity.revoked_at = datetime.now(timezone.utc)
    activity.revoked_by = actor.id
    activity.revoke_reason = reason

    audit_service.record(
        db,
        actor_id=actor.id,
        action="activity.revoke",
        resource_type="lead_activity",
        resource_id=str(activity.id),
        after={"revoke_reason": reason},
    )
    db.commit()
    return activity
