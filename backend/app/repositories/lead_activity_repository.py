"""跟进活动数据访问。"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead_activity import LeadActivity


def get_activity_by_id(db: Session, activity_id: uuid.UUID) -> LeadActivity | None:
    return db.get(LeadActivity, activity_id)


def get_activity_by_idempotency(
    db: Session, created_by: uuid.UUID, idempotency_key: str
) -> LeadActivity | None:
    return db.scalar(
        select(LeadActivity).where(
            LeadActivity.created_by == created_by,
            LeadActivity.idempotency_key == idempotency_key,
        )
    )


def create_activity(db: Session, activity: LeadActivity) -> LeadActivity:
    db.add(activity)
    db.flush()
    return activity


def list_activities(db: Session, lead_id: uuid.UUID) -> list[LeadActivity]:
    """返回有效事件（未撤销）。"""
    return list(
        db.scalars(
            select(LeadActivity)
            .where(LeadActivity.lead_id == lead_id, LeadActivity.revoked_at.is_(None))
            .order_by(LeadActivity.happened_at.desc(), LeadActivity.created_at.desc())
        ).all()
    )


def recent_followup_by_lead(
    db: Session, lead_ids: list[uuid.UUID]
) -> dict[uuid.UUID, datetime]:
    """批量取每个线索最近一次有效跟进时间（未撤销），供列表避免 N+1。"""
    if not lead_ids:
        return {}
    rows = db.execute(
        select(LeadActivity.lead_id, func.max(LeadActivity.happened_at))
        .where(
            LeadActivity.lead_id.in_(lead_ids),
            LeadActivity.revoked_at.is_(None),
        )
        .group_by(LeadActivity.lead_id)
    ).all()
    return {lead_id: latest for lead_id, latest in rows}
