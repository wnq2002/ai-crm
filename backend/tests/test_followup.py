"""跟进待办分类器与 todo 筛选测试。"""

from datetime import datetime, timedelta, timezone

from app.seed import seed_dictionaries
from app.services import followup_service as f
from tests.helpers import get_csrf, login, make_user


def _setup_admin(client_factory, db):
    make_user(db, "admin", "AdminPass123!", "admin")
    c = client_factory()
    login(c, "admin", "AdminPass123!")
    return c, get_csrf(c)


def test_classify_priority():
    now = datetime.now(timezone.utc)
    kw = dict(now=now, handoff_status="not_handed_off", outcome_status="unknown")

    # 已逾期优先于待首次跟进
    assert (
        f.classify(follow_up_count=0, next_follow_up_at=now - timedelta(days=1), last_followup_at=None, **kw)
        == "overdue"
    )
    # 待首次跟进
    assert f.classify(follow_up_count=0, next_follow_up_at=None, last_followup_at=None, **kw) == "first_follow"
    # 今日待跟进
    assert (
        f.classify(follow_up_count=1, next_follow_up_at=now, last_followup_at=now - timedelta(days=1), **kw)
        == "today"
    )
    # 多次跟进无进展（3 次、未交接、无反馈）
    assert (
        f.classify(follow_up_count=3, next_follow_up_at=None, last_followup_at=now - timedelta(hours=1), **kw)
        == "no_progress"
    )
    # 长期未更新（已交接、无反馈、10 天未跟进）
    assert (
        f.classify(
            follow_up_count=1,
            next_follow_up_at=None,
            last_followup_at=now - timedelta(days=10),
            handoff_status="handed_off",
            outcome_status="unknown",
            now=now,
        )
        == "stale"
    )
    # 交接待反馈（已交接、暂无反馈、2 天前刚跟进，未达长期未更新）
    assert (
        f.classify(
            follow_up_count=1,
            next_follow_up_at=None,
            last_followup_at=now - timedelta(days=2),
            handoff_status="handed_off",
            outcome_status="unknown",
            now=now,
        )
        == "handed_off_pending"
    )
    # 正常（下次在未来）
    assert (
        f.classify(
            follow_up_count=1,
            next_follow_up_at=now + timedelta(days=2),
            last_followup_at=now,
            **kw,
        )
        == "normal"
    )


def test_todo_order_includes_all_categories():
    assert set(f.TODO_ORDER) == {
        f.TODO_OVERDUE,
        f.TODO_FIRST_FOLLOW,
        f.TODO_TODAY,
        f.TODO_NO_PROGRESS,
        f.TODO_STALE,
        f.TODO_HANDED_OFF_PENDING,
    }


def test_create_activity_updates_next_follow_up_at(client_factory, db):
    seed_dictionaries(db)
    c, csrf = _setup_admin(client_factory, db)
    lead_id = c.post(
        "/api/v1/leads", json={"phone_raw": "13800001111"}, headers={"X-CSRF-Token": csrf}
    ).json()["lead"]["id"]

    nxt = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    c.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "result": "connected", "next_follow_up_at": nxt, "idempotency_key": "k1"},
        headers={"X-CSRF-Token": csrf},
    )
    d = c.get(f"/api/v1/leads/{lead_id}").json()
    assert d["next_follow_up_at"] is not None

    # 不设下次时间 → 清空
    c.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"kind": "phone", "result": "connected", "idempotency_key": "k2"},
        headers={"X-CSRF-Token": csrf},
    )
    d = c.get(f"/api/v1/leads/{lead_id}").json()
    assert d["next_follow_up_at"] is None


def test_todo_filter(client_factory, db):
    seed_dictionaries(db)
    c, csrf = _setup_admin(client_factory, db)
    lid = c.post(
        "/api/v1/leads", json={"phone_raw": "13800002222"}, headers={"X-CSRF-Token": csrf}
    ).json()["lead"]["id"]

    items = c.get("/api/v1/leads", params={"todo": "first_follow"}).json()["items"]
    assert any(x["id"] == lid for x in items)
    assert all(x["follow_up_status"] == "first_follow" for x in items)
    assert all(x["follow_up_count"] == 0 for x in items)
