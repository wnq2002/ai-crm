"""越权/RBAC 测试（服务端逐条校验，PRD §2 / architecture §8）。

V1.3 角色缩减为 admin/market（ADR-022），非管理员角色仅 market。
"""

from tests.helpers import get_csrf, login, make_user


def test_unauthenticated_admin_access(client, db):
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 401


def test_market_cannot_list_users(client, db):
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_market_cannot_create_user(client, db):
    make_user(db, "market1", "MarketPass123!", "market")
    login(client, "market1", "MarketPass123!")
    csrf = get_csrf(client)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "evil",
            "display_name": "Evil",
            "role": "admin",
            "password": "EvilPass123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 403
