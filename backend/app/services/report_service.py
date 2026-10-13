"""报表与工作台聚合（PRD §5.1/§5.7，api-contract §9）。"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.lead import (
    HANDOFF_HANDED_OFF,
    OUTCOME_IN_PROGRESS,
    OUTCOME_LOST,
    OUTCOME_UNKNOWN,
    OUTCOME_WON,
    QUALIFICATION_INVALID,
    QUALIFICATION_PENDING,
    QUALIFICATION_VALID,
    Lead,
)
from app.models.lead_activity import (
    ACTIVITY_KIND_PHONE,
    WECHAT_KINDS,
    LeadActivity,
)
from app.models.lead_event import LeadEvent, LeadHandoff, LeadOutcomeEvent
from app.models.lead_source import LeadSourceCategory
from app.models.user import User
from app.services import followup_service

SHANGHAI = ZoneInfo("Asia/Shanghai")


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return phone
    return phone[:3] + "****" + phone[-4:]


def mask_email(email: str | None) -> str:
    if not email:
        return ""
    local, _, domain = email.partition("@")
    if not domain:
        return email
    head = local[0] + "***" if local else ""
    return f"{head}@{domain}"


def to_shanghai(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(SHANGHAI).isoformat()


def _end_of_day(dt: datetime) -> datetime:
    """纯日期/午夜（无时分秒）视为该日结束，避免漏掉当天数据。"""
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def _lead_base(from_date: datetime | None, to_date: datetime | None):
    stmt = select(Lead).where(Lead.archived_at.is_(None))
    if from_date is not None:
        stmt = stmt.where(Lead.occurred_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Lead.occurred_at <= _end_of_day(to_date))
    return stmt


def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _distinct_companies(db: Session) -> int:
    return (
        db.scalar(
            select(func.count(func.distinct(Lead.company_id))).where(
                Lead.archived_at.is_(None), Lead.company_id.isnot(None)
            )
        )
        or 0
    )


def _phone_total(db: Session) -> int:
    return (
        db.scalar(
            select(func.count()).where(
                LeadActivity.kind == ACTIVITY_KIND_PHONE,
                LeadActivity.revoked_at.is_(None),
            )
        )
        or 0
    )


def _wechat_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count()).where(
                LeadActivity.kind.in_(WECHAT_KINDS),
                LeadActivity.revoked_at.is_(None),
            )
        )
        or 0
    )


def _build_todos(db: Session) -> tuple[dict, list[dict], list[dict]]:
    """构建待办计数、优先级排序的待办清单、最近新增线索。"""
    leads = list(db.scalars(select(Lead).where(Lead.archived_at.is_(None))).all())
    aggs = followup_service.followup_aggregates(db, [x.id for x in leads])

    counts = {
        followup_service.TODO_OVERDUE: 0,
        followup_service.TODO_FIRST_FOLLOW: 0,
        followup_service.TODO_TODAY: 0,
        followup_service.TODO_NO_PROGRESS: 0,
        followup_service.TODO_STALE: 0,
        followup_service.TODO_HANDED_OFF_PENDING: 0,
    }
    buckets: dict[str, list[Lead]] = {k: [] for k in counts}

    for lead in leads:
        agg = aggs.get(lead.id, {"follow_up_count": 0, "last_followup_at": None})
        cat = followup_service.classify(
            follow_up_count=agg["follow_up_count"],
            next_follow_up_at=lead.next_follow_up_at,
            last_followup_at=agg["last_followup_at"],
            handoff_status=lead.handoff_status,
            outcome_status=lead.outcome_status,
        )
        if cat == followup_service.TODO_NORMAL:
            continue
        counts[cat] += 1
        buckets[cat].append(lead)

    todo_list: list[dict] = []
    for cat in followup_service.TODO_ORDER:
        for lead in buckets[cat]:
            agg = aggs.get(lead.id, {"follow_up_count": 0, "last_followup_at": None})
            todo_list.append(
                {
                    "lead_id": str(lead.id),
                    "company_name_raw": lead.company_name_raw,
                    "contact_name_raw": lead.contact_name_raw,
                    "qualification_status": lead.qualification_status,
                    "outcome_status": lead.outcome_status,
                    "follow_up_count": agg["follow_up_count"],
                    "last_followup_at": agg["last_followup_at"],
                    "next_follow_up_at": lead.next_follow_up_at,
                    "todo": cat,
                }
            )

    recent_leads = [
        {
            "id": str(x.id),
            "company_name_raw": x.company_name_raw,
            "contact_name_raw": x.contact_name_raw,
            "occurred_at": x.occurred_at,
            "qualification_status": x.qualification_status,
        }
        for x in sorted(leads, key=lambda y: y.occurred_at, reverse=True)[:5]
    ]
    return counts, todo_list[:20], recent_leads


def dashboard_summary(
    db: Session, from_date: datetime | None, to_date: datetime | None
) -> dict:
    base = _lead_base(from_date, to_date)

    total_leads = _count(db, base)
    pending = _count(db, base.where(Lead.qualification_status == QUALIFICATION_PENDING))
    valid = _count(db, base.where(Lead.qualification_status == QUALIFICATION_VALID))
    handed_off = _count(db, base.where(Lead.handoff_status == HANDOFF_HANDED_OFF))
    no_feedback = _count(db, base.where(Lead.outcome_status == OUTCOME_UNKNOWN))
    won = _count(db, base.where(Lead.outcome_status == OUTCOME_WON))
    valid_not_handed_off = _count(
        db,
        base.where(
            Lead.qualification_status == QUALIFICATION_VALID,
            Lead.handoff_status != HANDOFF_HANDED_OFF,
        ),
    )
    handed_off_no_feedback = _count(
        db,
        base.where(
            Lead.handoff_status == HANDOFF_HANDED_OFF,
            Lead.outcome_status == OUTCOME_UNKNOWN,
        ),
    )

    todos, todo_list, recent_leads = _build_todos(db)
    return {
        "total_leads": total_leads,
        "distinct_companies": _distinct_companies(db),
        "pending": pending,
        "valid": valid,
        "handed_off": handed_off,
        "no_feedback": no_feedback,
        "won": won,
        "phone_total": _phone_total(db),
        "wechat_count": _wechat_count(db),
        "pending_to_confirm": pending,
        "valid_not_handed_off": valid_not_handed_off,
        "handed_off_no_feedback": handed_off_no_feedback,
        "todos": todos,
        "todo_list": todo_list,
        "recent_leads": recent_leads,
        "recent_events": recent_events(db),
    }


def overview(db: Session, from_date: datetime | None, to_date: datetime | None) -> dict:
    base = _lead_base(from_date, to_date)
    valid = _count(db, base.where(Lead.qualification_status == QUALIFICATION_VALID))
    invalid = _count(db, base.where(Lead.qualification_status == QUALIFICATION_INVALID))
    effective_rate = None
    if valid + invalid > 0:
        effective_rate = round(valid / (valid + invalid), 4)

    return {
        "total_leads": _count(db, base),
        "distinct_companies": _distinct_companies(db),
        "valid": valid,
        "invalid": invalid,
        "pending": _count(
            db, base.where(Lead.qualification_status == QUALIFICATION_PENDING)
        ),
        "effective_rate": effective_rate,
        "handed_off": _count(
            db, base.where(Lead.handoff_status == HANDOFF_HANDED_OFF)
        ),
        "outcome_won": _count(db, base.where(Lead.outcome_status == OUTCOME_WON)),
        "outcome_lost": _count(db, base.where(Lead.outcome_status == OUTCOME_LOST)),
        "outcome_in_progress": _count(
            db, base.where(Lead.outcome_status == OUTCOME_IN_PROGRESS)
        ),
        "no_feedback": _count(db, base.where(Lead.outcome_status == OUTCOME_UNKNOWN)),
    }


def sources(
    db: Session, from_date: datetime | None, to_date: datetime | None
) -> list[dict]:
    categories = db.scalars(
        select(LeadSourceCategory).order_by(LeadSourceCategory.created_at)
    ).all()
    result = []
    for cat in categories:
        cat_leads = _lead_base(from_date, to_date).where(
            Lead.source_category_id == cat.id
        )
        result.append(
            {
                "category_id": str(cat.id),
                "category_name": cat.name,
                "lead_count": _count(db, cat_leads),
                "valid_count": _count(
                    db,
                    cat_leads.where(Lead.qualification_status == QUALIFICATION_VALID),
                ),
                "handed_off_count": _count(
                    db, cat_leads.where(Lead.handoff_status == HANDOFF_HANDED_OFF)
                ),
            }
        )
    return result


def activities(
    db: Session, from_date: datetime | None, to_date: datetime | None
) -> list[dict]:
    base = (
        select(
            LeadActivity.created_by,
            User.display_name,
            func.count().label("total"),
            func.count()
            .filter(LeadActivity.kind == ACTIVITY_KIND_PHONE)
            .label("phone_total"),
        )
        .join(User, User.id == LeadActivity.created_by)
        .where(LeadActivity.revoked_at.is_(None))
    )
    if from_date is not None:
        base = base.where(LeadActivity.happened_at >= from_date)
    if to_date is not None:
        base = base.where(LeadActivity.happened_at <= _end_of_day(to_date))
    rows = db.execute(base.group_by(LeadActivity.created_by, User.display_name)).all()
    return [
        {
            "user_id": str(r[0]),
            "display_name": r[1],
            "total": r[2],
            "phone_total": r[3],
        }
        for r in rows
    ]


def handoffs(
    db: Session, from_date: datetime | None, to_date: datetime | None
) -> list[dict]:
    base = select(Department.name, func.count()).join(
        LeadHandoff, LeadHandoff.to_department_id == Department.id
    )
    if from_date is not None:
        base = base.where(LeadHandoff.happened_at >= from_date)
    if to_date is not None:
        base = base.where(LeadHandoff.happened_at <= _end_of_day(to_date))
    rows = db.execute(base.group_by(Department.name)).all()
    return [{"department": r[0], "count": r[1]} for r in rows]


def _as_shanghai(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SHANGHAI)
    return dt.astimezone(SHANGHAI)


def _default_range(
    from_date: datetime | None, to_date: datetime | None
) -> tuple[datetime, datetime]:
    now = datetime.now(SHANGHAI)
    if from_date is None:
        from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if to_date is None:
        to_date = now
    return from_date, to_date


def trend(
    db: Session, from_date: datetime | None, to_date: datetime | None
) -> dict:
    from_date, to_date = _default_range(from_date, to_date)

    lead_rows = db.execute(
        select(Lead.occurred_at, Lead.qualification_status).where(
            Lead.archived_at.is_(None),
            Lead.occurred_at >= from_date,
            Lead.occurred_at <= _end_of_day(to_date),
        )
    ).all()
    handoff_rows = db.execute(
        select(LeadHandoff.happened_at).where(
            LeadHandoff.happened_at >= from_date,
            LeadHandoff.happened_at <= _end_of_day(to_date),
        )
    ).all()

    leads_by_day: dict = {}
    valid_by_day: dict = {}
    handoffs_by_day: dict = {}
    for occurred_at, qualification_status in lead_rows:
        day = _as_shanghai(occurred_at).date()
        leads_by_day[day] = leads_by_day.get(day, 0) + 1
        if qualification_status == QUALIFICATION_VALID:
            valid_by_day[day] = valid_by_day.get(day, 0) + 1
    for (happened_at,) in handoff_rows:
        day = _as_shanghai(happened_at).date()
        handoffs_by_day[day] = handoffs_by_day.get(day, 0) + 1

    buckets = []
    day = _as_shanghai(from_date).date()
    end = _as_shanghai(to_date).date()
    while day <= end:
        buckets.append(
            {
                "date": day.isoformat(),
                "leads": leads_by_day.get(day, 0),
                "valid": valid_by_day.get(day, 0),
                "handed_off": handoffs_by_day.get(day, 0),
            }
        )
        day += timedelta(days=1)

    return {"buckets": buckets}


def safe_csv(value) -> str:
    """CSV 防公式注入：以 = + - @ 或制表符开头的单元格加单引号转义。"""
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def leads_export_rows(
    db: Session, from_date: datetime | None, to_date: datetime | None
) -> list[dict]:
    stmt = _lead_base(from_date, to_date).order_by(Lead.occurred_at.desc())
    rows = []
    for lead in db.scalars(stmt).all():
        rows.append(
            {
                "occurred_at": to_shanghai(lead.occurred_at),
                "company_name": lead.company_name_raw or "",
                "contact_name": lead.contact_name_raw or "",
                "phone": mask_phone(lead.phone_raw),
                "email": mask_email(lead.email_raw),
                "wechat": lead.wechat_raw or "",
                "need": lead.inquiry_text or "",
                "qualification_status": lead.qualification_status,
                "handoff_status": lead.handoff_status,
                "outcome_status": lead.outcome_status,
            }
        )
    return rows


def recent_events(db: Session, limit: int = 20) -> list[dict]:
    events = db.scalars(
        select(LeadEvent).order_by(LeadEvent.created_at.desc()).limit(limit)
    ).all()
    activities = db.scalars(
        select(LeadActivity).order_by(LeadActivity.created_at.desc()).limit(limit)
    ).all()
    handoffs = db.scalars(
        select(LeadHandoff).order_by(LeadHandoff.happened_at.desc()).limit(limit)
    ).all()
    outcomes = db.scalars(
        select(LeadOutcomeEvent)
        .order_by(LeadOutcomeEvent.feedback_at.desc())
        .limit(limit)
    ).all()

    raw = (
        [(e.event_type, e.created_at, e.created_by) for e in events]
        + [(a.kind, a.happened_at, a.created_by) for a in activities]
        + [("handoff", h.happened_at, h.created_by) for h in handoffs]
        + [("outcome", o.feedback_at, o.created_by) for o in outcomes]
    )
    raw.sort(key=lambda x: x[1], reverse=True)
    raw = raw[:limit]

    actor_ids = {r[2] for r in raw}
    users = {
        u.id: u.display_name
        for u in db.scalars(select(User).where(User.id.in_(actor_ids))).all()
    }
    return [
        {
            "event_type": event_type,
            "occurred_at": occurred_at,
            "actor_name": users.get(actor_id, ""),
        }
        for event_type, occurred_at, actor_id in raw
    ]
