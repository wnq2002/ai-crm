"""跟进待办分类器（工作台与线索列表共享）。

跟进真相源是 `lead_activities`：`follow_up_count` = 有效(未撤销)的沟通事件数
（排除 note），`last_followup_at` = 其中最近一次发生时间，均实时聚合、不落列。
唯一新增落列字段是 `leads.next_follow_up_at`（下次计划跟进时间）。
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead import (
    HANDOFF_HANDED_OFF,
    OUTCOME_IN_PROGRESS,
    OUTCOME_UNKNOWN,
    Lead,
)
from app.models.lead_activity import ACTIVITY_KIND_NOTE, LeadActivity

TODO_OVERDUE = "overdue"
TODO_FIRST_FOLLOW = "first_follow"
TODO_TODAY = "today"
TODO_NO_PROGRESS = "no_progress"
TODO_STALE = "stale"
TODO_HANDED_OFF_PENDING = "handed_off_pending"
TODO_NORMAL = "normal"

NO_PROGRESS_THRESHOLD = 3
STALE_DAYS = 7

# 工作台概览卡展示顺序（越靠前越需立即处理）
TODO_ORDER = [
    TODO_OVERDUE,
    TODO_FIRST_FOLLOW,
    TODO_TODAY,
    TODO_NO_PROGRESS,
    TODO_STALE,
    TODO_HANDED_OFF_PENDING,
]


def classify(
    *,
    follow_up_count: int,
    next_follow_up_at: datetime | None,
    last_followup_at: datetime | None,
    handoff_status: str,
    outcome_status: str,
    now: datetime | None = None,
) -> str:
    """按优先级返回唯一类别，避免同一线索在首页重复出现。

    优先级：已逾期 > 待首次跟进 > 今日待跟进 > 多次跟进无进展 > 长期未更新 > 正常。
    """
    now = now or datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    if next_follow_up_at is not None and next_follow_up_at < today_start:
        return TODO_OVERDUE
    if follow_up_count == 0:
        return TODO_FIRST_FOLLOW
    if next_follow_up_at is not None and today_start <= next_follow_up_at < today_end:
        return TODO_TODAY
    if (
        follow_up_count >= NO_PROGRESS_THRESHOLD
        and handoff_status != HANDOFF_HANDED_OFF
        and outcome_status == OUTCOME_UNKNOWN
    ):
        return TODO_NO_PROGRESS
    if (
        handoff_status == HANDOFF_HANDED_OFF
        and outcome_status in (OUTCOME_UNKNOWN, OUTCOME_IN_PROGRESS)
        and last_followup_at is not None
        and last_followup_at < now - timedelta(days=STALE_DAYS)
    ):
        return TODO_STALE
    if handoff_status == HANDOFF_HANDED_OFF and outcome_status == OUTCOME_UNKNOWN:
        return TODO_HANDED_OFF_PENDING
    return TODO_NORMAL


def followup_aggregates(
    db: Session, lead_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """批量聚合每线索的 follow_up_count / last_followup_at（排除 note、撤销）。"""
    if not lead_ids:
        return {}
    rows = db.execute(
        select(
            LeadActivity.lead_id,
            func.count().label("cnt"),
            func.max(LeadActivity.happened_at).label("last_at"),
        )
        .where(
            LeadActivity.lead_id.in_(lead_ids),
            LeadActivity.revoked_at.is_(None),
            LeadActivity.kind != ACTIVITY_KIND_NOTE,
        )
        .group_by(LeadActivity.lead_id)
    ).all()
    return {
        lead_id: {"follow_up_count": cnt, "last_followup_at": last_at}
        for lead_id, cnt, last_at in rows
    }


def _valid_followup_count():
    return (
        select(func.count())
        .where(
            LeadActivity.lead_id == Lead.id,
            LeadActivity.revoked_at.is_(None),
            LeadActivity.kind != ACTIVITY_KIND_NOTE,
        )
        .correlate(Lead)
        .scalar_subquery()
    )


def _last_followup_at():
    return (
        select(func.max(LeadActivity.happened_at))
        .where(
            LeadActivity.lead_id == Lead.id,
            LeadActivity.revoked_at.is_(None),
            LeadActivity.kind != ACTIVITY_KIND_NOTE,
        )
        .correlate(Lead)
        .scalar_subquery()
    )


def todo_condition(category: str):
    """返回用于 `select(Lead)` 的 SQLAlchemy 过滤条件。"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    cnt = _valid_followup_count()
    last_at = _last_followup_at()

    if category == TODO_OVERDUE:
        return Lead.next_follow_up_at < today_start
    if category == TODO_FIRST_FOLLOW:
        return cnt == 0
    if category == TODO_TODAY:
        return (Lead.next_follow_up_at >= today_start) & (
            Lead.next_follow_up_at < today_end
        )
    if category == TODO_NO_PROGRESS:
        return (
            (cnt >= NO_PROGRESS_THRESHOLD)
            & (Lead.handoff_status != HANDOFF_HANDED_OFF)
            & (Lead.outcome_status == OUTCOME_UNKNOWN)
        )
    if category == TODO_STALE:
        return (
            (Lead.handoff_status == HANDOFF_HANDED_OFF)
            & Lead.outcome_status.in_((OUTCOME_UNKNOWN, OUTCOME_IN_PROGRESS))
            & (last_at < now - timedelta(days=STALE_DAYS))
        )
    if category == TODO_HANDED_OFF_PENDING:
        # 已交接、暂无反馈，且未达「长期未更新」（最近跟进在 7 天内，或无跟进时间）
        not_stale = last_at.is_(None) | (
            last_at >= now - timedelta(days=STALE_DAYS)
        )
        return (
            (Lead.handoff_status == HANDOFF_HANDED_OFF)
            & (Lead.outcome_status == OUTCOME_UNKNOWN)
            & not_stale
        )
    raise ValueError(f"未知待办类别：{category}")
