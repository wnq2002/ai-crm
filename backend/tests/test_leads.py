"""线索创建与企业匹配测试（M3，api-contract §4/§5，V1.4 智能新增 + 重复检查）。"""

import uuid

from sqlalchemy import select

from app.models.company import Company
from app.models.lead_parse_record import LeadParseRecord
from app.seed import seed_dictionaries
from tests.helpers import get_csrf, login, make_user


def _setup_market(client, db) -> str:
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    return get_csrf(client)


def _create_company(db, name: str) -> Company:
    company = Company(canonical_name=name, normalized_name=name, aliases=[])
    db.add(company)
    db.commit()
    return company


def test_create_lead_no_company(client, db):
    csrf = _setup_market(client, db)
    r = client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000", "intake_method": "manual"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["lead"]["phone_raw"] == "13800138000"
    assert body["lead"]["company_id"] is None
    assert body["lead"]["qualification_status"] == "pending"
    assert body["company_candidates"] == []


def test_create_lead_auto_link_exact_company(client, db):
    csrf = _setup_market(client, db)
    company = _create_company(db, "广州云物智能科技")

    r = client.post(
        "/api/v1/leads",
        json={
            "company_name_raw": "广州云物智能科技",
            "contact_name_raw": "刘先生",
            "phone_raw": "13800138000",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["lead"]["company_id"] == str(company.id)
    assert body["company_candidates"] == []


def test_create_lead_returns_candidates(client, db):
    csrf = _setup_market(client, db)
    _create_company(db, "广州云物智能科技有限公司")

    r = client.post(
        "/api/v1/leads",
        json={"company_name_raw": "广州云物智能", "phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["lead"]["company_id"] is None
    assert len(body["company_candidates"]) >= 1


def test_create_lead_requires_identifiable_content(client, db):
    csrf = _setup_market(client, db)
    r = client.post(
        "/api/v1/leads",
        json={"intake_method": "manual"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_create_lead_idempotent(client, db):
    csrf = _setup_market(client, db)
    payload = {"phone_raw": "13800138000", "idempotency_key": "lead-k-1"}
    r1 = client.post("/api/v1/leads", json=payload, headers={"X-CSRF-Token": csrf})
    r2 = client.post("/api/v1/leads", json=payload, headers={"X-CSRF-Token": csrf})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["lead"]["id"] == r2.json()["lead"]["id"]


def test_create_lead_external_event_idempotent(client, db):
    csrf = _setup_market(client, db)
    payload = {"phone_raw": "13800138000", "external_source_event_id": "evt-1"}
    r1 = client.post("/api/v1/leads", json=payload, headers={"X-CSRF-Token": csrf})
    r2 = client.post("/api/v1/leads", json=payload, headers={"X-CSRF-Token": csrf})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["lead"]["id"] == r2.json()["lead"]["id"]


def test_update_lead_version_conflict(client, db):
    csrf = _setup_market(client, db)
    lead = client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]
    assert lead["version"] == 1

    r = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"inquiry_text": "v2", "version": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["version"] == 2

    r = client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"inquiry_text": "v3", "version": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "CONFLICT"


def test_list_and_filter_leads(client, db):
    csrf = _setup_market(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000", "inquiry_text": "需要 OPC Team"},
        headers={"X-CSRF-Token": csrf},
    )
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13900139000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/leads")
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r = client.get("/api/v1/leads", params={"q": "OPC"})
    assert r.json()["total"] == 1


def test_leads_list_masks_contact(client, db):
    csrf = _setup_market(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )
    r = client.get("/api/v1/leads")
    item = r.json()["items"][0]
    assert "phone_raw" not in item
    assert item["contact_summary"] == "138****8000"


def test_get_and_update_lead(client, db):
    csrf = _setup_market(client, db)
    lead_id = client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]["id"]

    r = client.get(f"/api/v1/leads/{lead_id}")
    assert r.status_code == 200

    r = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"inquiry_text": "补充需求", "version": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["inquiry_text"] == "补充需求"


def test_lead_notes_field(client, db):
    csrf = _setup_market(client, db)
    lead = client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000", "notes": "补充说明"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]
    assert lead["notes"] == "补充说明"


def test_lead_timestamps_are_utc(client, db):
    csrf = _setup_market(client, db)
    lead = client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    ).json()["lead"]

    for field in ("created_at", "updated_at", "occurred_at"):
        value = lead[field]
        assert value.endswith("Z") or value.endswith(
            "+00:00"
        ), f"{field} 非 UTC: {value}"


def test_archive_lead_admin_only(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    market_client = client_factory()
    login(market_client, "market1", "MarketPass123!")
    market_csrf = get_csrf(market_client)

    lead_id = market_client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": market_csrf},
    ).json()["lead"]["id"]

    # market 无归档权限
    r = market_client.post(
        f"/api/v1/leads/{lead_id}/archive", headers={"X-CSRF-Token": market_csrf}
    )
    assert r.status_code == 403

    admin_client = client_factory()
    login(admin_client, "admin", "AdminPass123!")
    admin_csrf = get_csrf(admin_client)
    r = admin_client.post(
        f"/api/v1/leads/{lead_id}/archive", headers={"X-CSRF-Token": admin_csrf}
    )
    assert r.status_code == 200
    assert r.json()["archived_at"] is not None


# ── M2 智能新增 + 重复检查 ──────────────────────────────


def _fake_extract(db, raw_text):
    return {
        "company_name": {"value": "广州云物智能", "confidence": "high"},
        "contact_name": {"value": "刘先生", "confidence": "high"},
        "phone": {"value": "13800138000", "confidence": "high"},
        "email": {"value": None, "confidence": None},
        "inquiry_text": {"value": "需要 OPC Team", "confidence": "medium"},
        "need_type": {"value": "OPC Team", "confidence": "high"},
        "source_channel": {"value": "官网", "confidence": "medium"},
        "hints": [],
    }


def test_parse_lead(client, db, monkeypatch):
    csrf = _setup_market(client, db)
    monkeypatch.setattr("app.ai.provider.extract_lead_fields", _fake_extract)

    r = client.post(
        "/api/v1/leads/parse",
        json={"raw_text": "广州云物智能 刘先生 13800138000 需要 OPC Team"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["company_name"]["value"] == "广州云物智能"
    assert body["company_name"]["confidence"] == "high"
    assert body["email"]["value"] is None
    assert body["need_type"]["value"] == "OPC Team"


def test_parse_lead_ai_unavailable(client, db):
    csrf = _setup_market(client, db)
    r = client.post(
        "/api/v1/leads/parse",
        json={"raw_text": "任意原文"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 503
    assert r.json()["code"] == "AI_UNAVAILABLE"


def test_parse_need_type_dict_filter(client, db, monkeypatch):
    csrf = _setup_market(client, db)

    def fake_extract(db, raw_text):
        result = _fake_extract(db, raw_text)
        result["need_type"] = {"value": "不存在的类型", "confidence": "high"}
        return result

    monkeypatch.setattr("app.ai.provider.extract_lead_fields", fake_extract)

    r = client.post(
        "/api/v1/leads/parse",
        json={"raw_text": "x"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["need_type"]["value"] is None
    assert any("需求类型未匹配" in h for h in body["hints"])


def test_create_lead_with_parse_record(client, db):
    csrf = _setup_market(client, db)
    raw = "广州云物智能 刘先生 13800138000 需要 OPC Team"
    r = client.post(
        "/api/v1/leads",
        json={
            "phone_raw": "13800138000",
            "parse_record": {
                "raw_text": raw,
                "parsed_json": {"company_name": {"value": "广州云物智能", "confidence": "high"}},
            },
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    lead_id = r.json()["lead"]["id"]

    records = db.scalars(
        select(LeadParseRecord).where(LeadParseRecord.lead_id == uuid.UUID(lead_id))
    ).all()
    assert len(records) == 1
    assert records[0].raw_text == raw
    assert records[0].parsed_json["company_name"]["value"] == "广州云物智能"


def test_create_lead_duplicate_phone_hint(client, db):
    csrf = _setup_market(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )
    r = client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000", "contact_name_raw": "张三"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    hints = r.json()["duplicate_hints"]
    assert any("手机号" in h for h in hints)


def test_duplicate_check_endpoint(client, db):
    csrf = _setup_market(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.post(
        "/api/v1/leads/duplicate-check",
        json={"phone_raw": "13800138000", "company_name_raw": "广州云物"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["contact_duplicate"] is True
    assert body["contact_hint"] is not None


def test_duplicate_check_company_and_external(client, db):
    csrf = _setup_market(client, db)
    _create_company(db, "广州云物智能科技")
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000", "external_source_event_id": "evt-9"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.post(
        "/api/v1/leads/duplicate-check",
        json={
            "company_name_raw": "广州云物智能",
            "external_source_event_id": "evt-9",
        },
        headers={"X-CSRF-Token": csrf},
    )
    body = r.json()
    assert len(body["company_candidates"]) >= 1
    assert body["external_event_conflict"] is True
