"""判断/交接/反馈业务逻辑（PRD §5.4/§6，api-contract §7）。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError, forbidden, not_found
from app.models.department import Department, DepartmentContact
from app.models.lead import (
    HANDOFF_HANDED_OFF,
    OUTCOME_LOST,
    OUTCOME_UNKNOWN,
    OUTCOME_WON,
    QUALIFICATION_INVALID,
    QUALIFICATION_VALID,
    Lead,
)
from app.models.lead_event import LeadEvent, LeadHandoff, LeadOutcomeEvent
from app.models.user import ROLE_ADMIN, User
from app.schemas.company import CompanyCreate
from app.schemas.decision import HandoffRequest, OutcomeRequest, QualificationRequest
from app.services import audit_service, company_service
from app.services.lead_service import get_lead


def _write_event(db, lead_id, actor_id, event_type, before=None, after=None):
    db.add(
        LeadEvent(
            lead_id=lead_id,
            event_type=event_type,
            before_json=before,
            after_json=after,
            created_by=actor_id,
        )
    )


def qualify(
    db: Session, actor: User, lead_id: uuid.UUID, payload: QualificationRequest
) -> Lead:
    lead = get_lead(db, lead_id)

    if lead.handoff_status == HANDOFF_HANDED_OFF and actor.role != ROLE_ADMIN:
        raise forbidden("已交接线索仅管理员可变更判断")

    if payload.qualification_status == QUALIFICATION_INVALID and not payload.reason:
        raise APIError(422, "VALIDATION_ERROR", "无效线索必须填写原因")

    before = lead.qualification_status
    lead.qualification_status = payload.qualification_status

    if (
        payload.qualification_status == QUALIFICATION_VALID
        and lead.company_id is None
        and lead.company_name_raw
    ):
        matched, _ = company_service.match_company(db, lead.company_name_raw)
        if matched is not None:
            lead.company_id = matched.id
        else:
            company = company_service.create_company(
                db, CompanyCreate(canonical_name=lead.company_name_raw)
            )
            lead.company_id = company.id

    _write_event(
        db,
        lead.id,
        actor.id,
        "lead.qualification",
        before={"status": before},
        after={"status": payload.qualification_status, "reason": payload.reason},
    )
    audit_service.record(
        db,
        actor_id=actor.id,
        action="lead.qualification",
        resource_type="lead",
        resource_id=str(lead.id),
        after={"status": payload.qualification_status},
    )
    db.commit()
    return lead


def _default_contact(db: Session, department_id: uuid.UUID) -> DepartmentContact | None:
    return db.scalar(
        select(DepartmentContact).where(
            DepartmentContact.department_id == department_id,
            DepartmentContact.is_default.is_(True),
        )
    )


def handoff(
    db: Session, actor: User, lead_id: uuid.UUID, payload: HandoffRequest
) -> Lead:
    lead = get_lead(db, lead_id)

    if lead.qualification_status != QUALIFICATION_VALID:
        raise APIError(422, "VALIDATION_ERROR", "仅有效线索可交接")

    department = db.get(Department, payload.department_id)
    if department is None:
        raise not_found("部门不存在")

    contact_id = payload.department_contact_id
    if contact_id is None:
        default_contact = _default_contact(db, department.id)
        contact_id = default_contact.id if default_contact else None
    if contact_id is None:
        raise APIError(422, "VALIDATION_ERROR", "该部门未配置对接人")

    old_department_id = lead.department_id
    db.add(
        LeadHandoff(
            lead_id=lead.id,
            from_department_id=old_department_id,
            to_department_id=department.id,
            to_contact_id=contact_id,
            note=payload.note,
            happened_at=datetime.now(timezone.utc),
            created_by=actor.id,
            reason=payload.reason,
        )
    )
    lead.handoff_status = HANDOFF_HANDED_OFF
    lead.department_id = department.id
    lead.department_contact_id = contact_id

    _write_event(
        db,
        lead.id,
        actor.id,
        "lead.handoff",
        before={"department_id": str(old_department_id) if old_department_id else None},
        after={"department_id": str(department.id), "contact_id": str(contact_id)},
    )

    audit_service.record(
        db,
        actor_id=actor.id,
        action="lead.handoff",
        resource_type="lead",
        resource_id=str(lead.id),
        after={"department_id": str(department.id), "contact_id": str(contact_id)},
    )
    db.commit()
    return lead


def outcome(
    db: Session, actor: User, lead_id: uuid.UUID, payload: OutcomeRequest
) -> Lead:
    lead = get_lead(db, lead_id)

    if (
        payload.outcome_status != OUTCOME_UNKNOWN
        and lead.handoff_status != HANDOFF_HANDED_OFF
    ):
        raise APIError(422, "VALIDATION_ERROR", "仅已交接线索可登记业务结果")

    if payload.outcome_status in (OUTCOME_WON, OUTCOME_LOST) and not payload.note:
        raise APIError(422, "VALIDATION_ERROR", "已成交/未成交需填写反馈依据")

    old_outcome = lead.outcome_status
    db.add(
        LeadOutcomeEvent(
            lead_id=lead.id,
            from_outcome=old_outcome,
            to_outcome=payload.outcome_status,
            note=payload.note,
            feedback_at=payload.feedback_at or datetime.now(timezone.utc),
            created_by=actor.id,
        )
    )
    lead.outcome_status = payload.outcome_status

    _write_event(
        db,
        lead.id,
        actor.id,
        "lead.outcome",
        before={"outcome": old_outcome},
        after={"outcome": payload.outcome_status},
    )

    audit_service.record(
        db,
        actor_id=actor.id,
        action="lead.outcome",
        resource_type="lead",
        resource_id=str(lead.id),
        after={"status": payload.outcome_status},
    )
    db.commit()
    return lead
