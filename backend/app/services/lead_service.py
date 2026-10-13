"""线索业务逻辑（PRD §5.2，api-contract §4，V1.4 智能新增 + 重复检查 + 统一时间线）。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import provider as ai_provider
from app.core.errors import APIError, conflict, not_found
from app.models.company import Company
from app.models.department import Department
from app.models.lead import INTAKE_MANUAL, Lead
from app.models.lead_activity import LeadActivity
from app.models.lead_event import LeadEvent, LeadHandoff, LeadOutcomeEvent
from app.models.lead_need_type import LeadNeedType
from app.models.lead_parse_record import LeadParseRecord
from app.models.lead_source import LeadSourceCategory
from app.models.user import User
from app.repositories import lead_repository
from app.schemas.lead import DuplicateCheckRequest, LeadCreate, LeadUpdate
from app.services import company_service
from app.services.normalization import normalize_email, normalize_phone
from app.services.report_service import mask_email, mask_phone

_PII_MASKERS = {
    "phone_raw": mask_phone,
    "email_raw": mask_email,
    "wechat_raw": lambda v: (v[:1] + "***") if v else v,
    "contact_name_raw": lambda v: (v[:1] + "***") if v else v,
}

EVENT_LEAD_CREATED = "lead.created"
EVENT_LEAD_UPDATED = "lead.updated"
EVENT_LEAD_ARCHIVED = "lead.archived"
EVENT_COMPANY_LINK = "lead.company_link"
EVENT_COMPANY_UNLINK = "lead.company_unlink"


def _default_source_category(db: Session) -> LeadSourceCategory:
    cat = db.scalar(
        select(LeadSourceCategory).where(LeadSourceCategory.code == "other")
    )
    if cat is None:
        raise APIError(500, "INTERNAL", "未初始化来源字典")
    return cat


def _validate_min_content(payload: LeadCreate) -> None:
    has_contact = any([payload.phone_raw, payload.email_raw, payload.wechat_raw])
    has_name = bool(payload.contact_name_raw or payload.company_name_raw)
    has_inquiry = bool(payload.inquiry_text)
    has_source_info = bool(payload.source_detail_id or payload.source_detail_text)
    has_external_event = bool(payload.external_source_event_id)

    ok = (
        has_contact
        or has_external_event
        or (has_name and has_source_info)
        or (has_inquiry and has_source_info)
    )
    if not ok:
        raise APIError(
            422,
            "VALIDATION_ERROR",
            "线索至少需要联系方式、姓名+来源、需求+来源或外部事件引用之一",
        )


def _write_event(
    db: Session,
    lead_id: uuid.UUID,
    actor_id: uuid.UUID,
    event_type: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        LeadEvent(
            lead_id=lead_id,
            event_type=event_type,
            before_json=before,
            after_json=after,
            created_by=actor_id,
        )
    )


def create_lead(
    db: Session, actor: User, payload: LeadCreate
) -> tuple[Lead, list[Company], list[str]]:
    _validate_min_content(payload)

    if payload.idempotency_key:
        existing = lead_repository.get_lead_by_idempotency_key(
            db, payload.idempotency_key
        )
        if existing is not None:
            return existing, [], []

    source_category_id = payload.source_category_id or _default_source_category(db).id

    # 同一渠道 external_source_event_id 重复推送 → 幂等复用已存在线索（不重复创建）
    if payload.external_source_event_id:
        existing = lead_repository.get_lead_by_external_event(
            db, source_category_id, payload.external_source_event_id
        )
        if existing is not None:
            return existing, [], []

    duplicate_hints: list[str] = []
    hint = _contact_duplicate_hint(db, payload.phone_raw, payload.email_raw)
    if hint:
        duplicate_hints.append(hint)

    occurred_at = payload.occurred_at or datetime.now(timezone.utc)

    lead = Lead(
        company_name_raw=payload.company_name_raw,
        contact_name_raw=payload.contact_name_raw,
        phone_raw=payload.phone_raw,
        email_raw=payload.email_raw,
        wechat_raw=payload.wechat_raw,
        need_type_id=payload.need_type_id,
        inquiry_text=payload.inquiry_text,
        notes=payload.notes,
        occurred_at=occurred_at,
        source_category_id=source_category_id,
        source_detail_id=payload.source_detail_id,
        source_detail_text=payload.source_detail_text,
        intake_method=payload.intake_method or INTAKE_MANUAL,
        external_source_event_id=payload.external_source_event_id,
        idempotency_key=payload.idempotency_key,
        created_by=actor.id,
    )
    lead_repository.create_lead(db, lead)
    _write_event(db, lead.id, actor.id, EVENT_LEAD_CREATED)

    # 随附 AI 解析记录：原文必保留，lead_id 创建后回填
    if payload.parse_record is not None:
        db.add(
            LeadParseRecord(
                lead_id=lead.id,
                raw_text=payload.parse_record.raw_text,
                parsed_json=payload.parse_record.parsed_json,
                created_by=actor.id,
            )
        )

    matched, candidates = company_service.match_company(db, payload.company_name_raw)
    if matched is not None:
        lead.company_id = matched.id
        _write_event(
            db,
            lead.id,
            actor.id,
            EVENT_COMPANY_LINK,
            after={"company_id": str(matched.id)},
        )

    db.commit()
    return lead, candidates, duplicate_hints


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = lead_repository.get_lead_by_id(db, lead_id)
    if lead is None or lead.archived_at is not None:
        raise not_found("线索不存在")
    return lead


def lead_list_item(
    lead: Lead,
    recent_followup_at: datetime | None = None,
    follow_up_count: int = 0,
    follow_up_status: str = "normal",
) -> dict:
    summary = None
    if lead.phone_raw:
        summary = mask_phone(lead.phone_raw)
    elif lead.email_raw:
        summary = mask_email(lead.email_raw)
    elif lead.wechat_raw:
        summary = lead.wechat_raw[:1] + "***"
    return {
        "id": lead.id,
        "occurred_at": lead.occurred_at,
        "company_name_raw": lead.company_name_raw,
        "contact_name_raw": lead.contact_name_raw,
        "contact_summary": summary,
        "need_type_id": lead.need_type_id,
        "inquiry_text": lead.inquiry_text,
        "qualification_status": lead.qualification_status,
        "handoff_status": lead.handoff_status,
        "outcome_status": lead.outcome_status,
        "department_id": lead.department_id,
        "department_contact_id": lead.department_contact_id,
        "source_category_id": lead.source_category_id,
        "source_detail_id": lead.source_detail_id,
        "source_detail_text": lead.source_detail_text,
        "recent_followup_at": recent_followup_at,
        "next_follow_up_at": lead.next_follow_up_at,
        "follow_up_count": follow_up_count,
        "follow_up_status": follow_up_status,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


def list_leads(db: Session, **kwargs) -> tuple[list[Lead], int]:
    return lead_repository.list_leads(db, **kwargs)


def update_lead(
    db: Session, actor: User, lead_id: uuid.UUID, payload: LeadUpdate
) -> Lead:
    lead = get_lead(db, lead_id)

    if payload.version is not None and payload.version != lead.version:
        raise conflict(
            "线索已被他人修改，请刷新后重试", {"current_version": lead.version}
        )

    changes: dict[str, str] = {}
    fields = [
        "occurred_at",
        "contact_name_raw",
        "phone_raw",
        "email_raw",
        "wechat_raw",
        "company_name_raw",
        "need_type_id",
        "inquiry_text",
        "notes",
        "source_category_id",
        "source_detail_id",
        "source_detail_text",
    ]
    for field in fields:
        new_value = getattr(payload, field)
        if new_value is not None:
            old_value = getattr(lead, field)
            setattr(lead, field, new_value)
            mask = _PII_MASKERS.get(field)
            changes[field] = {
                "from": mask(str(old_value)) if mask else str(old_value),
                "to": mask(str(new_value)) if mask else str(new_value),
            }

    if changes:
        lead.version += 1
        _write_event(db, lead.id, actor.id, EVENT_LEAD_UPDATED, after=changes)
        db.commit()

    return lead


def archive_lead(db: Session, actor: User, lead_id: uuid.UUID) -> Lead:
    lead = get_lead(db, lead_id)
    if lead.archived_at is not None:
        return lead

    lead.archived_at = datetime.now(timezone.utc)
    _write_event(db, lead.id, actor.id, EVENT_LEAD_ARCHIVED)
    db.commit()
    return lead


def unarchive_lead(db: Session, actor: User, lead_id: uuid.UUID) -> Lead:
    lead = lead_repository.get_lead_by_id(db, lead_id)
    if lead is None:
        raise not_found("线索不存在")
    if lead.archived_at is None:
        return lead

    lead.archived_at = None
    _write_event(db, lead.id, actor.id, "lead.unarchived")
    db.commit()
    return lead


def link_company(
    db: Session,
    actor: User,
    lead_id: uuid.UUID,
    company_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
) -> Lead:
    lead = get_lead(db, lead_id)
    company = company_service.link_company(db, lead, company_id, contact_id)
    _write_event(
        db,
        lead.id,
        actor.id,
        EVENT_COMPANY_LINK,
        after={"company_id": str(company.id)},
    )
    db.commit()
    return lead


def unlink_company(db: Session, actor: User, lead_id: uuid.UUID) -> Lead:
    lead = get_lead(db, lead_id)
    before = str(lead.company_id) if lead.company_id else None
    company_service.unlink_company(lead)
    _write_event(
        db, lead.id, actor.id, EVENT_COMPANY_UNLINK, before={"company_id": before}
    )
    db.commit()
    return lead


def match_candidates(db: Session, lead_id: uuid.UUID) -> list[Company]:
    lead = get_lead(db, lead_id)
    _, candidates = company_service.match_company(db, lead.company_name_raw)
    return candidates


# ── M2 智能新增线索 ─────────────────────────────────────


def _match_need_type(db: Session, name: str) -> str | None:
    needle = name.strip().lower()
    rows = db.scalars(
        select(LeadNeedType).where(LeadNeedType.active.is_(True))
    ).all()
    for row in rows:
        if row.name.strip().lower() == needle:
            return row.name
    return None


def parse_lead_text(db: Session, raw_text: str) -> dict:
    """AI 提取字段；`需求类型` 仅在系统字典 `lead_need_types` 匹配时才返回，否则置空。"""
    extracted = ai_provider.extract_lead_fields(db, raw_text)

    need_type = extracted.get("need_type") or {}
    value = (need_type.get("value") or "").strip()
    if value:
        matched = _match_need_type(db, value)
        if matched is None:
            need_type["value"] = None
            need_type["confidence"] = None
            extracted.setdefault("hints", []).append("需求类型未匹配系统字典，已置空")
        else:
            need_type["value"] = matched
    return extracted


# ── 重复检查 ───────────────────────────────────────────


def _contact_duplicate_hint(
    db: Session, phone: str | None, email: str | None
) -> str | None:
    """手机号/邮箱规范化后比对历史线索，命中即提示疑似同一联系人（不泄露对方 PII）。"""
    nphone = normalize_phone(phone)
    nemail = normalize_email(email)
    if not nphone and not nemail:
        return None
    leads = db.scalars(select(Lead).where(Lead.archived_at.is_(None))).all()
    for lead in leads:
        if nphone and lead.phone_raw and normalize_phone(lead.phone_raw) == nphone:
            return "存在相同手机号的历史线索，可能为同一联系人"
        if nemail and lead.email_raw and normalize_email(lead.email_raw) == nemail:
            return "存在相同邮箱的历史线索，可能为同一联系人"
    return None


def _company_candidate_list(db: Session, company_name: str | None) -> list[Company]:
    matched, candidates = company_service.match_company(db, company_name)
    result: list[Company] = []
    if matched is not None:
        result.append(matched)
    result.extend(candidates)
    return result


def check_duplicates(db: Session, payload: DuplicateCheckRequest) -> dict:
    """创建前重复检查：联系人/企业/渠道四类情形。"""
    contact_duplicate = False
    contact_hint = None
    hint = _contact_duplicate_hint(db, payload.phone_raw, payload.email_raw)
    if hint:
        contact_duplicate = True
        contact_hint = hint

    company_candidates = _company_candidate_list(db, payload.company_name_raw)

    external_event_conflict = False
    if payload.external_source_event_id:
        source_category_id = payload.source_category_id or _default_source_category(db).id
        existing = lead_repository.get_lead_by_external_event(
            db, source_category_id, payload.external_source_event_id
        )
        external_event_conflict = existing is not None

    return {
        "contact_duplicate": contact_duplicate,
        "contact_hint": contact_hint,
        "company_candidates": company_candidates,
        "external_event_conflict": external_event_conflict,
    }


# ── 统一时间线 ─────────────────────────────────────────


def _user_names(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: u.display_name for u in rows}


def _department_names(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.scalars(select(Department).where(Department.id.in_(ids))).all()
    return {d.id: d.name for d in rows}


def build_timeline(db: Session, lead_id: uuid.UUID) -> list[dict]:
    """统一时间线：创建 / 电话 / 微信申请 / 微信通过 / 微信沟通 / 备注 /
    有效性变化 / 部门移交 / 部门反馈，按实际发生时间倒序。"""
    lead = get_lead(db, lead_id)
    items: list[dict] = []

    items.append(
        {
            "id": str(lead.id),
            "type": "lead_created",
            "result": None,
            "content": lead.contact_name_raw or lead.company_name_raw,
            "happened_at": lead.occurred_at,
            "recorded_at": lead.created_at,
            "created_by": lead.created_by,
        }
    )

    activities = db.scalars(
        select(LeadActivity).where(
            LeadActivity.lead_id == lead_id, LeadActivity.revoked_at.is_(None)
        )
    ).all()
    for a in activities:
        items.append(
            {
                "id": str(a.id),
                "type": a.kind,
                "result": a.result,
                "content": a.content,
                "happened_at": a.happened_at,
                "recorded_at": a.created_at,
                "created_by": a.created_by,
            }
        )

    for e in db.scalars(
        select(LeadEvent).where(
            LeadEvent.lead_id == lead_id, LeadEvent.event_type == "lead.qualification"
        )
    ).all():
        after = e.after_json or {}
        items.append(
            {
                "id": str(e.id),
                "type": "qualification",
                "result": after.get("status"),
                "content": after.get("reason"),
                "happened_at": e.created_at,
                "recorded_at": e.created_at,
                "created_by": e.created_by,
            }
        )

    handoffs = db.scalars(
        select(LeadHandoff).where(LeadHandoff.lead_id == lead_id)
    ).all()
    dept_names = _department_names(db, {h.to_department_id for h in handoffs})
    for h in handoffs:
        items.append(
            {
                "id": str(h.id),
                "type": "handoff",
                "result": "handed_off",
                "content": dept_names.get(h.to_department_id),
                "happened_at": h.happened_at,
                "recorded_at": h.created_at,
                "created_by": h.created_by,
            }
        )

    outcomes = db.scalars(
        select(LeadOutcomeEvent).where(LeadOutcomeEvent.lead_id == lead_id)
    ).all()
    for o in outcomes:
        items.append(
            {
                "id": str(o.id),
                "type": "outcome",
                "result": o.to_outcome,
                "content": o.note,
                "happened_at": o.feedback_at,
                "recorded_at": o.created_at,
                "created_by": o.created_by,
            }
        )

    user_names = _user_names(db, {it["created_by"] for it in items if it["created_by"]})
    for it in items:
        it["created_by_name"] = user_names.get(it["created_by"])

    items.sort(key=lambda x: (x["happened_at"], x["recorded_at"]), reverse=True)
    return items
