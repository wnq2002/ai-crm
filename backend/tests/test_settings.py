"""配置字典路由测试（api-contract §10，market 只读 / admin 可写）。"""

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.seed import seed_dictionaries
from tests.helpers import get_csrf, login, make_user

AI_URL = "https://api.openai.com/v1"
SECRET = "sk-test-secret-123"


def _setup_admin(client_factory, db):
    make_user(db, "admin", "AdminPass123!", "admin")
    c = client_factory()
    login(c, "admin", "AdminPass123!")
    return c, get_csrf(c)


def _ai_payload(**overrides):
    payload = {
        "provider": "openai",
        "endpoint": AI_URL,
        "model": "gpt-4o",
        "api_key": SECRET,
        "timeout_seconds": 30,
    }
    payload.update(overrides)
    return payload


def _setup_market(client, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")


def test_market_can_read_dictionaries(client, db):
    _setup_market(client, db)

    assert len(client.get("/api/v1/settings/departments").json()) == 3
    assert len(client.get("/api/v1/settings/department-contacts").json()) == 3
    assert len(client.get("/api/v1/settings/source-categories").json()) == 2
    assert len(client.get("/api/v1/settings/need-types").json()) == 2


def test_market_read_does_not_require_csrf(client, db):
    _setup_market(client, db)
    r = client.get("/api/v1/settings/source-categories")
    assert r.status_code == 200


def test_market_cannot_write_dictionaries(client, db):
    _setup_market(client, db)
    csrf = get_csrf(client)
    r = client.post(
        "/api/v1/settings/departments",
        json={"name": "新部门"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 403


def test_admin_can_write_dictionaries(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "admin", "AdminPass123!", "admin")
    c = client_factory()
    login(c, "admin", "AdminPass123!")
    csrf = get_csrf(c)

    r = c.post(
        "/api/v1/settings/departments",
        json={"name": "新部门"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "新部门"

    r = c.patch(
        f"/api/v1/settings/departments/{r.json()['id']}",
        json={"active": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["active"] is False


# ── AI 配置（ADR-029）──────────────────────────────────
def test_market_can_read_ai_config(client, db):
    _setup_market(client, db)
    r = client.get("/api/v1/settings/ai")
    assert r.status_code == 200
    assert r.json()["api_key_configured"] is False


def test_market_cannot_write_ai_config(client, db):
    _setup_market(client, db)
    csrf = get_csrf(client)
    r = client.put(
        "/api/v1/settings/ai",
        json=_ai_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 403

    r = client.post(
        "/api/v1/settings/ai",
        json=_ai_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 403


def test_admin_write_ai_config_success_and_key_masked(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)

    r = c.put(
        "/api/v1/settings/ai",
        json=_ai_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o"
    assert body["api_key_configured"] is True
    assert body["api_key"] == "***configured***"
    assert SECRET not in str(body)

    # GET 同样不回传明文密钥
    g = c.get("/api/v1/settings/ai")
    assert g.status_code == 200
    assert g.json()["api_key"] == "***configured***"
    assert SECRET not in str(g.json())


def test_ai_config_write_requires_csrf(client_factory, db):
    c, _ = _setup_admin(client_factory, db)
    r = c.put("/api/v1/settings/ai", json=_ai_payload())
    assert r.status_code == 403


def test_ai_config_invalid_endpoint_returns_422(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)
    r = c.put(
        "/api/v1/settings/ai",
        json=_ai_payload(endpoint="not-a-url"),
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_ai_config_invalid_timeout_returns_422(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)
    r = c.put(
        "/api/v1/settings/ai",
        json=_ai_payload(timeout_seconds=0),
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


def test_ai_config_key_preserved_when_not_resend(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)
    assert (
        c.put(
            "/api/v1/settings/ai",
            json=_ai_payload(),
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 200
    )

    # 仅改 model，不重传 api_key → 密钥应保留
    r = c.put(
        "/api/v1/settings/ai",
        json=_ai_payload(model="gpt-4o-mini", api_key=None),
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "gpt-4o-mini"
    assert r.json()["api_key_configured"] is True


def test_ai_config_audit_log_masks_key(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)
    c.put(
        "/api/v1/settings/ai",
        json=_ai_payload(),
        headers={"X-CSRF-Token": csrf},
    )

    logs = db.scalars(
        select(AuditLog).where(AuditLog.action == "settings.ai_update")
    ).all()
    assert len(logs) == 1
    assert SECRET not in (logs[0].before_json or "")
    assert SECRET not in (logs[0].after_json or "")
    assert "***configured***" in (logs[0].after_json or "")


# ── 配置写操作审计 ─────────────────────────────────────
def test_department_write_is_audited(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)
    r = c.post(
        "/api/v1/settings/departments",
        json={"name": "审计部"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    dept_id = r.json()["id"]

    logs = db.scalars(
        select(AuditLog).where(
            AuditLog.action == "department.create",
            AuditLog.resource_id == dept_id,
        )
    ).all()
    assert len(logs) == 1

    c.patch(
        f"/api/v1/settings/departments/{dept_id}",
        json={"active": False},
        headers={"X-CSRF-Token": csrf},
    )
    logs = db.scalars(
        select(AuditLog).where(AuditLog.action == "department.update")
    ).all()
    assert len(logs) == 1
    assert logs[0].before_json is not None
    assert logs[0].after_json is not None


# ── 删除（引用保护）与批量改派 ─────────────────────────
def test_delete_unreferenced_dictionary(client_factory, db):
    c, csrf = _setup_admin(client_factory, db)
    r = c.post(
        "/api/v1/settings/need-types",
        json={"name": "待删类型"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    nt_id = r.json()["id"]

    r = c.delete(
        f"/api/v1/settings/need-types/{nt_id}", headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 204


def test_delete_referenced_department_conflict(client_factory, db):
    seed_dictionaries(db)
    c, csrf = _setup_admin(client_factory, db)

    dept = c.post(
        "/api/v1/settings/departments",
        json={"name": "待删部门"},
        headers={"X-CSRF-Token": csrf},
    ).json()
    contact = c.post(
        "/api/v1/settings/department-contacts",
        json={"department_id": dept["id"], "name": "对接", "is_default": True},
        headers={"X-CSRF-Token": csrf},
    ).json()

    lead = c.post(
        "/api/v1/leads",
        json={"phone_raw": "13800007777"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]
    c.post(
        f"/api/v1/leads/{lead['id']}/qualification",
        json={"qualification_status": "valid"},
        headers={"X-CSRF-Token": csrf},
    )
    c.post(
        f"/api/v1/leads/{lead['id']}/handoff",
        json={"department_id": dept["id"], "department_contact_id": contact["id"]},
        headers={"X-CSRF-Token": csrf},
    )

    r = c.delete(
        f"/api/v1/settings/departments/{dept['id']}", headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 409


def test_reassign_contact_leads(client_factory, db):
    seed_dictionaries(db)
    c, csrf = _setup_admin(client_factory, db)

    dept = c.post(
        "/api/v1/settings/departments",
        json={"name": "改派部门"},
        headers={"X-CSRF-Token": csrf},
    ).json()
    a = c.post(
        "/api/v1/settings/department-contacts",
        json={"department_id": dept["id"], "name": "A", "is_default": True},
        headers={"X-CSRF-Token": csrf},
    ).json()
    b = c.post(
        "/api/v1/settings/department-contacts",
        json={"department_id": dept["id"], "name": "B"},
        headers={"X-CSRF-Token": csrf},
    ).json()

    lead = c.post(
        "/api/v1/leads",
        json={"phone_raw": "13800007778"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]
    c.post(
        f"/api/v1/leads/{lead['id']}/qualification",
        json={"qualification_status": "valid"},
        headers={"X-CSRF-Token": csrf},
    )
    c.post(
        f"/api/v1/leads/{lead['id']}/handoff",
        json={"department_id": dept["id"], "department_contact_id": a["id"]},
        headers={"X-CSRF-Token": csrf},
    )

    r = c.post(
        f"/api/v1/settings/department-contacts/{a['id']}/reassign",
        json={"to_contact_id": b["id"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["moved_leads"] == 1

    d = c.get(f"/api/v1/leads/{lead['id']}").json()
    assert d["department_contact_id"] == b["id"]
