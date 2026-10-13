"""判断/交接/反馈测试（M6，api-contract §7）。"""

from sqlalchemy import func, select

from app.models.company import Company
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


def _qualify(client, csrf, lead_id, status):
    return client.post(
        f"/api/v1/leads/{lead_id}/qualification",
        json={"qualification_status": status},
        headers={"X-CSRF-Token": csrf},
    )


def _handoff(client, csrf, lead_id, dept_id):
    return client.post(
        f"/api/v1/leads/{lead_id}/handoff",
        json={"department_id": dept_id},
        headers={"X-CSRF-Token": csrf},
    )


def test_qualify_valid(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    r = _qualify(client, csrf, lead_id, "valid")
    assert r.status_code == 200
    assert r.json()["qualification_status"] == "valid"


def test_qualify_invalid_requires_reason(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    r = client.post(
        f"/api/v1/leads/{lead_id}/qualification",
        json={"qualification_status": "invalid"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_handoff_requires_valid(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    dept_id = client.get("/api/v1/settings/departments").json()[0]["id"]
    r = _handoff(client, csrf, lead_id, dept_id)
    assert r.status_code == 422


def test_handoff_success(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    _qualify(client, csrf, lead_id, "valid")
    dept_id = client.get("/api/v1/settings/departments").json()[0]["id"]
    r = _handoff(client, csrf, lead_id, dept_id)
    assert r.status_code == 200
    assert r.json()["handoff_status"] == "handed_off"
    assert r.json()["department_id"] == dept_id


def test_outcome_requires_handed_off(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    r = client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome_status": "won", "note": "已签约"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_outcome_won_requires_note(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    _qualify(client, csrf, lead_id, "valid")
    dept_id = client.get("/api/v1/settings/departments").json()[0]["id"]
    _handoff(client, csrf, lead_id, dept_id)

    r = client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome_status": "won"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_outcome_success(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    _qualify(client, csrf, lead_id, "valid")
    dept_id = client.get("/api/v1/settings/departments").json()[0]["id"]
    _handoff(client, csrf, lead_id, dept_id)

    r = client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome_status": "won", "note": "已签约"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["outcome_status"] == "won"


def test_qualify_admin_only_after_handoff(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    mc = client_factory()
    login(mc, "market1", "MarketPass123!")
    mcsrf = get_csrf(mc)
    lead_id = _make_lead(mc, mcsrf)
    _qualify(mc, mcsrf, lead_id, "valid")
    dept_id = mc.get("/api/v1/settings/departments").json()[0]["id"]
    _handoff(mc, mcsrf, lead_id, dept_id)

    # handed_off 后 market 改 qualification → 403
    r = mc.post(
        f"/api/v1/leads/{lead_id}/qualification",
        json={"qualification_status": "invalid", "reason": "重新评估"},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert r.status_code == 403

    # admin 可改
    ac = client_factory()
    login(ac, "admin", "AdminPass123!")
    acsrf = get_csrf(ac)
    r = ac.post(
        f"/api/v1/leads/{lead_id}/qualification",
        json={"qualification_status": "invalid", "reason": "重新评估"},
        headers={"X-CSRF-Token": acsrf},
    )
    assert r.status_code == 200
    assert r.json()["qualification_status"] == "invalid"


def test_outcome_deferred(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    _qualify(client, csrf, lead_id, "valid")
    dept_id = client.get("/api/v1/settings/departments").json()[0]["id"]
    _handoff(client, csrf, lead_id, dept_id)

    r = client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome_status": "deferred", "note": "暂缓推进"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["outcome_status"] == "deferred"


def test_outcome_deferred_requires_handed_off(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    r = client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome_status": "deferred"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_timeline_includes_decision_events(client, db):
    csrf = _setup(client, db)
    lead_id = _make_lead(client, csrf)
    _qualify(client, csrf, lead_id, "valid")
    dept_id = client.get("/api/v1/settings/departments").json()[0]["id"]
    _handoff(client, csrf, lead_id, dept_id)
    client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome_status": "won", "note": "已签约"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get(f"/api/v1/leads/{lead_id}/timeline")
    assert r.status_code == 200
    types = {item["type"] for item in r.json()}
    assert {"qualification", "handoff", "outcome"} <= types


def test_qualify_valid_auto_creates_company(client, db):
    csrf = _setup(client, db)
    r = client.post(
        "/api/v1/leads",
        json={"company_name_raw": "广州云物智能科技", "phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )
    lead_id = r.json()["lead"]["id"]

    r = _qualify(client, csrf, lead_id, "valid")
    assert r.status_code == 200
    assert r.json()["company_id"] is not None

    company = db.scalar(
        select(Company).where(Company.canonical_name == "广州云物智能科技")
    )
    assert company is not None
    assert str(company.id) == r.json()["company_id"]


def test_qualify_valid_links_existing_company(client, db):
    csrf = _setup(client, db)
    r = client.post(
        "/api/v1/leads",
        json={"company_name_raw": "广州云物智能科技", "phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )
    lead_id = r.json()["lead"]["id"]

    company = Company(
        canonical_name="广州云物智能科技", normalized_name="广州云物智能科技", aliases=[]
    )
    db.add(company)
    db.commit()

    r = _qualify(client, csrf, lead_id, "valid")
    assert r.status_code == 200
    assert r.json()["company_id"] == str(company.id)

    count = db.scalar(select(func.count()).select_from(Company)) or 0
    assert count == 1
