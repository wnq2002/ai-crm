"""线索数据访问。"""

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.services import followup_service


def get_lead_by_id(db: Session, lead_id: uuid.UUID) -> Lead | None:
    return db.get(Lead, lead_id)


def get_lead_by_idempotency_key(db: Session, key: str) -> Lead | None:
    return db.scalar(select(Lead).where(Lead.idempotency_key == key))


def get_lead_by_external_event(
    db: Session, source_category_id: uuid.UUID, external_event_id: str
) -> Lead | None:
    return db.scalar(
        select(Lead).where(
            Lead.source_category_id == source_category_id,
            Lead.external_source_event_id == external_event_id,
        )
    )


def create_lead(db: Session, lead: Lead) -> Lead:
    db.add(lead)
    db.flush()
    return lead


def list_leads(
    db: Session,
    *,
    q: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    source_category_id: uuid.UUID | None,
    need_type_id: uuid.UUID | None,
    qualification_status: str | None,
    handoff_status: str | None,
    outcome_status: str | None,
    department_id: uuid.UUID | None,
    archived_only: bool,
    todo: str | None,
    page: int,
    page_size: int,
    sort: str,
) -> tuple[list[Lead], int]:
    if archived_only:
        stmt = select(Lead).where(Lead.archived_at.isnot(None))
    else:
        stmt = select(Lead).where(Lead.archived_at.is_(None))

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Lead.company_name_raw.ilike(like),
                Lead.contact_name_raw.ilike(like),
                Lead.phone_raw.ilike(like),
                Lead.email_raw.ilike(like),
                Lead.inquiry_text.ilike(like),
            )
        )
    if occurred_from is not None:
        stmt = stmt.where(Lead.occurred_at >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(Lead.occurred_at <= occurred_to)
    if source_category_id is not None:
        stmt = stmt.where(Lead.source_category_id == source_category_id)
    if need_type_id is not None:
        stmt = stmt.where(Lead.need_type_id == need_type_id)
    if qualification_status is not None:
        stmt = stmt.where(Lead.qualification_status == qualification_status)
    if handoff_status is not None:
        stmt = stmt.where(Lead.handoff_status == handoff_status)
    if outcome_status is not None:
        stmt = stmt.where(Lead.outcome_status == outcome_status)
    if department_id is not None:
        stmt = stmt.where(Lead.department_id == department_id)
    if todo is not None:
        stmt = stmt.where(followup_service.todo_condition(todo))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order = (
        Lead.occurred_at.desc() if sort == "-occurred_at" else Lead.occurred_at.asc()
    )
    stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)
    rows = list(db.scalars(stmt).all())
    return rows, total
