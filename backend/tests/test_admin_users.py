"""管理员用户管理测试（api-contract §11）。"""

from tests.helpers import get_csrf, login, make_user


def _admin_csrf(client, db) -> str:
    make_user(db, "admin", "AdminPass123!", "admin")
    login(client, "admin", "AdminPass123!")
    return get_csrf(client)


def test_list_users_admin_only(client, db):
    _admin_csrf(client, db)
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["items"][0]["username"] == "admin"


def test_create_user(client, db):
    csrf = _admin_csrf(client, db)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "sales1",
            "display_name": "Sales One",
            "role": "market",
            "password": "SalesPass123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "market"
    assert body["is_active"] is True
    assert body["must_change_password"] is True


def test_create_user_duplicate_username(client, db):
    csrf = _admin_csrf(client, db)
    payload = {
        "username": "sales1",
        "display_name": "Sales One",
        "role": "market",
        "password": "SalesPass123!",
    }
    assert (
        client.post(
            "/api/v1/admin/users", json=payload, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 200
    )
    r = client.post("/api/v1/admin/users", json=payload, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 409
    assert r.json()["code"] == "CONFLICT"


def test_create_user_password_too_short(client, db):
    csrf = _admin_csrf(client, db)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "sales1",
            "display_name": "Sales One",
            "role": "market",
            "password": "short",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_create_user_rejects_sales_role(client, db):
    # V1.3 弃用 sales 角色（ADR-022）：白名单仅 admin|market
    csrf = _admin_csrf(client, db)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "sales1",
            "display_name": "Sales One",
            "role": "sales",
            "password": "SalesPass123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_create_user_invalid_role(client, db):
    csrf = _admin_csrf(client, db)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "sales1",
            "display_name": "Sales One",
            "role": "superuser",
            "password": "SalesPass123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_disable_user_revokes_session(client_factory, db):
    make_user(db, "admin", "AdminPass123!", "admin")
    sales = make_user(db, "sales1", "SalesPass123!", "market")

    admin_client = client_factory()
    sales_client = client_factory()

    login(admin_client, "admin", "AdminPass123!")
    admin_csrf = get_csrf(admin_client)

    assert login(sales_client, "sales1", "SalesPass123!").status_code == 200
    assert sales_client.get("/api/v1/auth/me").status_code == 200

    r = admin_client.patch(
        f"/api/v1/admin/users/{sales.id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # 禁用后已登录会话立即失效，且无法再登录
    assert sales_client.get("/api/v1/auth/me").status_code == 401
    assert login(sales_client, "sales1", "SalesPass123!").status_code == 401


def test_reset_password_forces_change(client, db):
    csrf = _admin_csrf(client, db)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "sales1",
            "display_name": "Sales One",
            "role": "market",
            "password": "SalesPass123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    user_id = r.json()["id"]

    r2 = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"new_password": "ResetPass456!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 200
    assert r2.json()["must_change_password"] is True


def test_assign_role(client, db):
    csrf = _admin_csrf(client, db)
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "sales1",
            "display_name": "Sales One",
            "role": "market",
            "password": "SalesPass123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    user_id = r.json()["id"]

    r2 = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 200
    assert r2.json()["role"] == "admin"


def test_update_user_not_found(client, db):
    csrf = _admin_csrf(client, db)
    r = client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"
