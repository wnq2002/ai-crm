"""企业客户管理测试（M4，api-contract §5）。"""

from app.seed import seed_dictionaries
from tests.helpers import get_csrf, login, make_user


def _setup_market(client, db) -> str:
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    return get_csrf(client)


def _create_company(client, csrf, name, industry=None):
    payload = {"canonical_name": name}
    if industry:
        payload["industry"] = industry
    return client.post(
        "/api/v1/companies", json=payload, headers={"X-CSRF-Token": csrf}
    ).json()["id"]


def test_create_and_list_companies(client, db):
    csrf = _setup_market(client, db)
    r = client.post(
        "/api/v1/companies",
        json={
            "canonical_name": "广州云物智能科技",
            "industry": "软件",
            "phone": "020-12345678",
            "website": "https://example.com",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "020-12345678"
    assert r.json()["website"] == "https://example.com"

    r = client.get("/api/v1/companies")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["canonical_name"] == "广州云物智能科技"
    assert body["items"][0]["lead_count"] == 0


def test_company_detail_with_leads(client, db):
    csrf = _setup_market(client, db)
    cid = _create_company(client, csrf, "A公司")

    # 建线索并自动关联（企业名精确匹配）
    client.post(
        "/api/v1/leads",
        json={"company_name_raw": "A公司", "phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get(f"/api/v1/companies/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["canonical_name"] == "A公司"
    assert len(body["leads"]) == 1
    assert body["leads"][0]["phone_raw"] == "13800138000"


def test_update_company(client, db):
    csrf = _setup_market(client, db)
    cid = _create_company(client, csrf, "A公司")

    r = client.patch(
        f"/api/v1/companies/{cid}",
        json={"industry": "制造业", "aliases": ["别名A"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["industry"] == "制造业"
    assert r.json()["aliases"] == ["别名A"]


def test_merge_companies_admin_only(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    market_client = client_factory()
    login(market_client, "market1", "MarketPass123!")
    market_csrf = get_csrf(market_client)

    src = _create_company(market_client, market_csrf, "源公司")
    dst = _create_company(market_client, market_csrf, "目标公司")

    # market 无合并权限
    r = market_client.post(
        "/api/v1/companies/merge",
        json={"source_company_id": src, "target_company_id": dst},
        headers={"X-CSRF-Token": market_csrf},
    )
    assert r.status_code == 403

    admin_client = client_factory()
    login(admin_client, "admin", "AdminPass123!")
    admin_csrf = get_csrf(admin_client)
    r = admin_client.post(
        "/api/v1/companies/merge",
        json={"source_company_id": src, "target_company_id": dst},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert r.status_code == 200
    assert r.json()["merged_company_id"] == dst


def test_company_contacts_crud(client, db):
    csrf = _setup_market(client, db)
    cid = _create_company(client, csrf, "A公司")

    r = client.post(
        f"/api/v1/companies/{cid}/contacts",
        json={"name": "张三", "phone": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    contact_id = r.json()["id"]

    assert len(client.get(f"/api/v1/companies/{cid}/contacts").json()) == 1

    r = client.patch(
        f"/api/v1/contacts/{contact_id}",
        json={"email": "a@b.com"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"


def test_merge_preview(client_factory, db):
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    make_user(db, "admin", "AdminPass123!", "admin")

    mc = client_factory()
    login(mc, "market1", "MarketPass123!")
    csrf = get_csrf(mc)
    src = _create_company(mc, csrf, "源公司")
    dst = _create_company(mc, csrf, "目标公司")
    mc.post(
        "/api/v1/leads",
        json={"company_name_raw": "源公司", "phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    ac = client_factory()
    login(ac, "admin", "AdminPass123!")
    acsrf = get_csrf(ac)
    r = ac.post(
        "/api/v1/companies/merge-preview",
        json={"source_company_id": src, "target_company_id": dst},
        headers={"X-CSRF-Token": acsrf},
    )
    assert r.status_code == 200
    assert r.json()["lead_relink_count"] == 1
    assert r.json()["alias_destination"] == "目标公司"
