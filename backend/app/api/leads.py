"""线索路由（api-contract §4/§5）。"""

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf, require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.activity import ActivityCreate, ActivityOut
from app.schemas.common import Page
from app.schemas.company import CompanyOut
from app.schemas.decision import HandoffRequest, OutcomeRequest, QualificationRequest
from app.schemas.lead import (
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    LeadCreate,
    LeadCreateResponse,
    LeadListItem,
    LeadOut,
    LeadParseRequest,
    LeadParseResponse,
    LeadUpdate,
    LinkCompanyRequest,
)
from app.services import (
    activity_service,
    audit_service,
    decision_service,
    followup_service,
    lead_service,
    report_service,
)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=Page[LeadListItem])
def list_leads(
    q: str | None = Query(default=None),
    occurred_from: datetime | None = Query(default=None),
    occurred_to: datetime | None = Query(default=None),
    source_category_id: uuid.UUID | None = Query(default=None),
    need_type_id: uuid.UUID | None = Query(default=None),
    qualification_status: str | None = Query(default=None),
    handoff_status: str | None = Query(default=None),
    outcome_status: str | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    archived: bool = Query(default=False),
    todo: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="-occurred_at"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows, total = lead_service.list_leads(
        db,
        q=q,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        source_category_id=source_category_id,
        need_type_id=need_type_id,
        qualification_status=qualification_status,
        handoff_status=handoff_status,
        outcome_status=outcome_status,
        department_id=department_id,
        archived_only=archived,
        todo=todo,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    aggs = followup_service.followup_aggregates(db, [lead.id for lead in rows])
    items = []
    for lead in rows:
        agg = aggs.get(lead.id, {"follow_up_count": 0, "last_followup_at": None})
        status = followup_service.classify(
            follow_up_count=agg["follow_up_count"],
            next_follow_up_at=lead.next_follow_up_at,
            last_followup_at=agg["last_followup_at"],
            handoff_status=lead.handoff_status,
            outcome_status=lead.outcome_status,
        )
        items.append(
            lead_service.lead_list_item(
                lead,
                recent_followup_at=agg["last_followup_at"],
                follow_up_count=agg["follow_up_count"],
                follow_up_status=status,
            )
        )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("", response_model=LeadCreateResponse)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    lead, candidates, duplicate_hints = lead_service.create_lead(db, actor, payload)
    return {
        "lead": lead,
        "company_candidates": candidates,
        "duplicate_hints": duplicate_hints,
    }


@router.post("/parse", response_model=LeadParseResponse)
def parse_lead(
    payload: LeadParseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    return lead_service.parse_lead_text(db, payload.raw_text)


@router.post("/duplicate-check", response_model=DuplicateCheckResponse)
def duplicate_check(
    payload: DuplicateCheckRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    return lead_service.check_duplicates(db, payload)


@router.get("/export")
def export_leads(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    audit_service.record(
        db,
        actor_id=actor.id,
        action="lead.export",
        resource_type="lead",
        resource_id=None,
    )
    db.commit()
    rows = report_service.leads_export_rows(db, from_, to)
    headers = [
        "occurred_at",
        "company_name",
        "contact_name",
        "phone",
        "email",
        "wechat",
        "need",
        "qualification_status",
        "handoff_status",
        "outcome_status",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([report_service.safe_csv(r[h]) for h in headers])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads_export.csv"'},
    )


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lead = lead_service.get_lead(db, lead_id)
    summary = activity_service.get_followup_summary(db, lead_id)
    out = LeadOut.model_validate(lead)
    out.phone_total_count = summary["phone_total_count"]
    out.wechat_count = summary["wechat_count"]
    out.recent_followup_at = summary["recent_followup_at"]
    out.wechat_relationship = activity_service.get_wechat_relationship(db, lead_id)
    return out


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return lead_service.update_lead(db, actor, lead_id, payload)


@router.post("/{lead_id}/archive", response_model=LeadOut)
def archive_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    return lead_service.archive_lead(db, actor, lead_id)


@router.post("/{lead_id}/unarchive", response_model=LeadOut)
def unarchive_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    return lead_service.unarchive_lead(db, actor, lead_id)


@router.get("/{lead_id}/company-candidates", response_model=list[CompanyOut])
def company_candidates(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return lead_service.match_candidates(db, lead_id)


@router.post("/{lead_id}/link-company", response_model=LeadOut)
def link_company(
    lead_id: uuid.UUID,
    payload: LinkCompanyRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return lead_service.link_company(
        db, actor, lead_id, payload.company_id, payload.contact_id
    )


@router.delete("/{lead_id}/company-link", response_model=LeadOut)
def unlink_company(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return lead_service.unlink_company(db, actor, lead_id)


@router.get("/{lead_id}/activities", response_model=list[ActivityOut])
def list_activities(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lead_service.get_lead(db, lead_id)
    return activity_service.list_activities(db, lead_id)


@router.post("/{lead_id}/activities", response_model=ActivityOut)
def create_activity(
    lead_id: uuid.UUID,
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return activity_service.create_activity(db, actor, lead_id, payload)


@router.post("/{lead_id}/qualification", response_model=LeadOut)
def qualify(
    lead_id: uuid.UUID,
    payload: QualificationRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return decision_service.qualify(db, actor, lead_id, payload)


@router.post("/{lead_id}/handoff", response_model=LeadOut)
def handoff(
    lead_id: uuid.UUID,
    payload: HandoffRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return decision_service.handoff(db, actor, lead_id, payload)


@router.post("/{lead_id}/outcome", response_model=LeadOut)
def outcome(
    lead_id: uuid.UUID,
    payload: OutcomeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return decision_service.outcome(db, actor, lead_id, payload)


@router.get("/{lead_id}/timeline")
def timeline(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return lead_service.build_timeline(db, lead_id)
