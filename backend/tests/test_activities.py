"""跟进活动测试（M5，api-contract §6，V1.4 三态微信 + 事件修正）。"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.lead_event_revision import LeadEventRevision
from app.seed import seed_dictionaries
from tests.helpers import get_csrf, login, make_user


def _setup(client, db) -> str:
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    return get_csrf(client)


def _make_lead(client, csrf) -> str:
    return client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]["id"]


def test_create_phone_activity(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    r = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "result": "connected", "idempotency_key": "a1"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["kind"] == "phone"
    assert r.json()["result"] == "connected"


def test_create_wechat_activity_no_result(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    r = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "wechat_request", "idempotency_key": "a2"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["result"] is None


def test_activity_validation(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    # phone 但 result 非法 → 422
    r = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "result": "bogus", "idempotency_key": "a3"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422

    # phone 但缺 result → 422（服务端校验）
    r = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "idempotency_key": "a3b"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422

    # wechat 但带 result → 422
    r = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={
            "kind": "wechat_request",
            "result": "connected",
            "idempotency_key": "a4",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_activity_idempotent(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    payload = {"kind": "phone", "result": "connected", "idempotency_key": "dup"}
    r1 = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    r2 = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert r1.json()["id"] == r2.json()["id"]


def test_revoke_activity_creator_or_admin(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "market2", "Market2Pass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    mc = client_factory()
    login(mc, "market1", "MarketPass123!")
    mcsrf = get_csrf(mc)
    lead_id = _make_lead(mc, mcsrf)
    activity_id = mc.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "result": "unconnected", "idempotency_key": "r1"},
        headers={"X-CSRF-Token": mcsrf},
    ).json()["id"]

    # 非创建者的其他 market 无权限
    other = client_factory()
    login(other, "market2", "Market2Pass123!")
    r = other.post(
        f"/api/v1/activities/{activity_id}/revoke",
        json={"reason": "误操作"},
        headers={"X-CSRF-Token": get_csrf(other)},
    )
    assert r.status_code == 403

    # 创建者本人可撤销
    r = mc.post(
        f"/api/v1/activities/{activity_id}/revoke",
        json={"reason": "误操作"},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert r.status_code == 200
    assert r.json()["revoked_at"] is not None


def test_revoke_activity_admin_can_revoke_any(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    mc = client_factory()
    login(mc, "market1", "MarketPass123!")
    mcsrf = get_csrf(mc)
    lead_id = _make_lead(mc, mcsrf)
    activity_id = mc.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "note", "idempotency_key": "r2"},
        headers={"X-CSRF-Token": mcsrf},
    ).json()["id"]

    ac = client_factory()
    login(ac, "admin", "AdminPass123!")
    acsrf = get_csrf(ac)
    r = ac.post(
        f"/api/v1/activities/{activity_id}/revoke",
        json={"reason": "误操作"},
        headers={"X-CSRF-Token": acsrf},
    )
    assert r.status_code == 200
    assert r.json()["revoked_at"] is not None


def test_activity_happened_at_future_rejected(client, db):
    from datetime import datetime, timedelta, timezone

    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    r = client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "note", "happened_at": future, "idempotency_key": "f1"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_timeline_includes_activities(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "result": "connected", "idempotency_key": "t1"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get(f"/api/v1/leads/{lead_id}/timeline")
    assert r.status_code == 200
    types = {item["type"] for item in r.json()}
    assert "lead_created" in types
    assert "phone" in types


def _post_activity(client, csrf, lead_id, kind, key, **extra):
    return client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": kind, "idempotency_key": key, **extra},
        headers={"X-CSRF-Token": csrf},
    )


def test_wechat_relationship_derivation(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    assert client.get(f"/api/v1/leads/{lead_id}").json()["wechat_relationship"] == "none"

    _post_activity(client, csrf, lead_id, "wechat_request", "w1")
    assert client.get(f"/api/v1/leads/{lead_id}").json()["wechat_relationship"] == "pending"

    _post_activity(client, csrf, lead_id, "wechat_approved", "w2")
    assert client.get(f"/api/v1/leads/{lead_id}").json()["wechat_relationship"] == "approved"


def test_wechat_chat_requires_approved(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    r = _post_activity(client, csrf, lead_id, "wechat_chat", "c1", content="你好")
    assert r.status_code == 422

    _post_activity(client, csrf, lead_id, "wechat_request", "w1")
    _post_activity(client, csrf, lead_id, "wechat_approved", "w2")

    r = _post_activity(client, csrf, lead_id, "wechat_chat", "c1", content="你好")
    assert r.status_code == 200
    assert r.json()["kind"] == "wechat_chat"


def test_wechat_approved_creates_new_event_not_modify_history(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    req = _post_activity(client, csrf, lead_id, "wechat_request", "w1").json()
    appr = _post_activity(client, csrf, lead_id, "wechat_approved", "w2").json()

    assert req["id"] != appr["id"]
    assert appr["kind"] == "wechat_approved"

    acts = client.get(f"/api/v1/leads/{lead_id}/activities").json()
    kinds = {a["kind"] for a in acts}
    assert {"wechat_request", "wechat_approved"} <= kinds


def test_activity_happened_at_near_future_rejected(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    near_future = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    r = _post_activity(
        client, csrf, lead_id, "note", "nf1", happened_at=near_future
    )
    assert r.status_code == 422


def test_phone_count_aggregation(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    _post_activity(client, csrf, lead_id, "phone", "p1", result="connected")
    _post_activity(client, csrf, lead_id, "phone", "p2", result="unconnected")

    assert client.get(f"/api/v1/leads/{lead_id}").json()["phone_total_count"] == 2


def test_revise_activity(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)

    a = _post_activity(client, csrf, lead_id, "phone", "rv1", result="connected").json()

    r = client.patch(
        f"/api/v1/activities/{a['id']}",
        json={"result": "unconnected", "content": "更正", "reason": "误填"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["result"] == "unconnected"
    assert r.json()["content"] == "更正"

    revisions = db.scalars(
        select(LeadEventRevision).where(
            LeadEventRevision.activity_id == uuid.UUID(a["id"])
        )
    ).all()
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev.reason == "误填"
    assert rev.before_json["result"] == "connected"
    assert rev.after_json["result"] == "unconnected"


def test_revise_activity_permission(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "market2", "Market2Pass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    mc = client_factory()
    login(mc, "market1", "MarketPass123!")
    mcsrf = get_csrf(mc)
    lead_id = _make_lead(mc, mcsrf)
    a = _post_activity(mc, mcsrf, lead_id, "phone", "rv2", result="connected").json()

    other = client_factory()
    login(other, "market2", "Market2Pass123!")
    r = other.patch(
        f"/api/v1/activities/{a['id']}",
        json={"result": "rejected", "reason": "更正"},
        headers={"X-CSRF-Token": get_csrf(other)},
    )
    assert r.status_code == 403

    ac = client_factory()
    login(ac, "admin", "AdminPass123!")
    r = ac.patch(
        f"/api/v1/activities/{a['id']}",
        json={"result": "rejected", "reason": "更正"},
        headers={"X-CSRF-Token": get_csrf(ac)},
    )
    assert r.status_code == 200
    assert r.json()["result"] == "rejected"


def test_revise_activity_validation(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    a = _post_activity(client, csrf, lead_id, "phone", "rv3", result="connected").json()

    # 缺少 reason
    r = client.patch(
        f"/api/v1/activities/{a['id']}",
        json={"result": "rejected"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422

    # 无任何修正项
    r = client.patch(
        f"/api/v1/activities/{a['id']}",
        json={"reason": "无变更"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422

    # 未来时间
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = client.patch(
        f"/api/v1/activities/{a['id']}",
        json={"reason": "补录", "happened_at": future},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_revise_activity_non_phone_cannot_set_result(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    a = _post_activity(client, csrf, lead_id, "note", "rv4", content="备注").json()

    r = client.patch(
        f"/api/v1/activities/{a['id']}",
        json={"result": "connected", "reason": "误加结果"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
