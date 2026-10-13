"""工作台/报表/导出测试（M7，api-contract §9/§8）。"""

from app.seed import seed_dictionaries
from tests.helpers import get_csrf, login, make_user


def _setup(client, db) -> str:
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    return get_csrf(client)


def test_dashboard_summary(client, db):
    csrf = _setup(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_leads"] == 1
    assert body["pending_to_confirm"] == 1
    assert isinstance(body["recent_events"], list)


def test_reports_overview(client, db):
    csrf = _setup(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/reports/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_leads"] == 1
    assert body["outcome_won"] == 0
    assert body["effective_rate"] is None


def test_reports_sources(client, db):
    csrf = _setup(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/reports/sources")
    assert r.status_code == 200
    sources = r.json()
    assert isinstance(sources, list)
    assert sources and sources[0]["category_name"]
    assert "lead_count" in sources[0]
    assert "valid_count" in sources[0]
    assert "handed_off_count" in sources[0]


def test_dashboard_trend(client, db):
    csrf = _setup(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/dashboard/trend")
    assert r.status_code == 200
    buckets = r.json()["buckets"]
    assert isinstance(buckets, list)
    assert buckets
    assert all(
        {"date", "leads", "valid", "handed_off"} <= set(b.keys())
        for b in buckets
    )
    assert sum(b["leads"] for b in buckets) == 1


def test_leads_export_csv(client, db):
    csrf = _setup(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "13800138000", "company_name_raw": "A公司"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/leads/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


def test_leads_export_formula_injection(client, db):
    csrf = _setup(client, db)
    client.post(
        "/api/v1/leads",
        json={"phone_raw": "=cmd()", "company_name_raw": "+公司"},
        headers={"X-CSRF-Token": csrf},
    )

    r = client.get("/api/v1/leads/export")
    body = r.text
    # 公式注入防护：= 和 + 开头的单元格加单引号转义
    assert "'=cmd()" in body
    assert "'+公司" in body
