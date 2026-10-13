"""V1.3 业务模型约束测试（PRD §7 / architecture §5）。"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.lead import Lead
from app.models.lead_activity import LeadActivity
from app.models.lead_source import LeadSourceCategory
from tests.helpers import make_user


def _make_lead(db, user_id) -> Lead:
    cat = db.scalar(
        select(LeadSourceCategory).where(LeadSourceCategory.code == "other")
    )
    if cat is None:
        cat = LeadSourceCategory(code="other", name="其他")
        db.add(cat)
        db.flush()
    lead = Lead(
        occurred_at=datetime.now(timezone.utc),
        source_category_id=cat.id,
        intake_method="manual",
        created_by=user_id,
    )
    db.add(lead)
    db.flush()
    return lead


def test_lead_activity_phone_result(db):
    user = make_user(db, "m1", "Pass12345", "market")
    lead = _make_lead(db, user.id)

    # 电话事件带联系结果（connected/unconnected/rejected）
    for result in ("connected", "unconnected", "rejected"):
        db.add(
            LeadActivity(
                lead_id=lead.id,
                kind="phone",
                result=result,
                happened_at=datetime.now(timezone.utc),
                created_by=user.id,
                idempotency_key=f"k{result}",
            )
        )
    db.commit()

    rows = db.scalars(select(LeadActivity)).all()
    assert {r.result for r in rows} == {"connected", "unconnected", "rejected"}


def test_lead_activity_wechat_no_result(db):
    user = make_user(db, "m1", "Pass12345", "market")
    lead = _make_lead(db, user.id)

    # 微信事件不写联系结果（result 为 NULL）
    db.add(
        LeadActivity(
            lead_id=lead.id,
            kind="wechat_request",
            happened_at=datetime.now(timezone.utc),
            created_by=user.id,
            idempotency_key="wx",
        )
    )
    db.commit()

    a = db.scalar(select(LeadActivity).where(LeadActivity.idempotency_key == "wx"))
    assert a.result is None
