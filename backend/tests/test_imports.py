"""线索导入测试（M3，api-contract §8）。"""

from app.seed import seed_dictionaries
from tests.helpers import get_csrf, login, make_user

CSV = (
    "获取时间,姓名,手机号,邮箱,微信号,企业名称,需求类型,需求描述,来源类型,来源详情\n"
    "2026-10-10,刘先生,13800138000,,,广州云物智能科技,AI Agent,需要OPC Team,官网,\n"
    "2026-10-11,陈女士,13900139000,,,,,,其他,\n"
)


def _setup(client, db) -> str:
    seed_dictionaries(db)
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    return get_csrf(client)


def test_import_template(client, db):
    _setup(client, db)
    r = client.get("/api/v1/imports/template")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_import_preview_and_commit(client, db):
    csrf = _setup(client, db)
    files = {"file": ("leads.csv", CSV.encode("utf-8"), "text/csv")}

    r = client.post(
        "/api/v1/imports/preview", files=files, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 200
    preview = r.json()
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["errors"] == []

    r = client.post(
        "/api/v1/imports/commit",
        json={"preview_token": preview["preview_token"], "idempotency_key": "batch-1"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["success_rows"] == 2

    r = client.get("/api/v1/leads")
    assert r.json()["total"] == 2


def test_import_commit_idempotent(client, db):
    csrf = _setup(client, db)
    files = {"file": ("leads.csv", CSV.encode("utf-8"), "text/csv")}
    preview = client.post(
        "/api/v1/imports/preview", files=files, headers={"X-CSRF-Token": csrf}
    ).json()

    r1 = client.post(
        "/api/v1/imports/commit",
        json={"preview_token": preview["preview_token"], "idempotency_key": "batch-x"},
        headers={"X-CSRF-Token": csrf},
    )
    r2 = client.post(
        "/api/v1/imports/commit",
        json={"preview_token": "stale-token", "idempotency_key": "batch-x"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["batch_id"] == r2.json()["batch_id"]

    # 批次幂等：重试不重复导入
    assert client.get("/api/v1/leads").json()["total"] == 2


def test_import_row_error(client, db):
    csrf = _setup(client, db)
    csv = (
        "获取时间,姓名,手机号,邮箱,微信号,企业名称,需求类型,需求描述,来源类型,来源详情\n"
        + "\n"
    )
    # 空行被跳过；再补一行只有姓名无法区分 → 应报错
    csv = (
        "获取时间,姓名,手机号,邮箱,微信号,企业名称,需求类型,需求描述,来源类型,来源详情\n"
        "2026-10-10,张三,,,,,,,,,\n"
    )
    files = {"file": ("leads.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post(
        "/api/v1/imports/preview", files=files, headers={"X-CSRF-Token": csrf}
    )
    assert r.status_code == 200
    assert r.json()["valid_rows"] == 0
    assert len(r.json()["errors"]) == 1


def test_import_no_source_defaults_to_unknown(client, db):
    """只有联系方式、未填来源类型的导入行不得 500，应默认归入「未知」来源。"""
    csrf = _setup(client, db)
    csv = (
        "获取时间,姓名,手机号,邮箱,微信号,企业名称,需求类型,需求描述,来源类型,来源详情\n"
        "2026-10-10,,13811110004,,,,,,,,\n"
    )
    files = {"file": ("leads.csv", csv.encode("utf-8"), "text/csv")}
    preview = client.post(
        "/api/v1/imports/preview", files=files, headers={"X-CSRF-Token": csrf}
    ).json()
    assert preview["valid_rows"] == 1

    r = client.post(
        "/api/v1/imports/commit",
        json={"preview_token": preview["preview_token"], "idempotency_key": "batch-no-source"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["success_rows"] == 1

    items = client.get("/api/v1/leads").json()["items"]
    assert len(items) == 1
    assert items[0]["source_category_id"] is not None
