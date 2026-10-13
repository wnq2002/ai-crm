"""认证端点测试（api-contract §2 / ADR-016）。"""

from tests.helpers import get_csrf, login, make_user


def test_login_success(client, db):
    make_user(db, "sales1", "SalesPass123!", "market")
    r = login(client, "sales1", "SalesPass123!")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "sales1"
    assert body["role"] == "market"
    assert "ai_crm_session" in client.cookies
    assert "csrf_token" in client.cookies
    assert get_csrf(client)


def test_login_wrong_password(client, db):
    make_user(db, "sales1", "SalesPass123!", "market")
    r = login(client, "sales1", "wrong-password")
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHORIZED"


def test_login_unknown_username(client, db):
    r = login(client, "ghost", "whatever123")
    assert r.status_code == 401


def test_login_inactive_user(client, db):
    make_user(db, "disabled", "SalesPass123!", "market", is_active=False)
    r = login(client, "disabled", "SalesPass123!")
    assert r.status_code == 401


def test_login_rate_limited(client, db):
    make_user(db, "sales1", "SalesPass123!", "market")
    for _ in range(5):
        r = login(client, "sales1", "wrong-password")
        assert r.status_code == 401
    r = login(client, "sales1", "wrong-password")
    assert r.status_code == 429
    assert r.json()["code"] == "RATE_LIMITED"


def test_me_unauthenticated(client, db):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_authenticated(client, db):
    make_user(db, "sales1", "SalesPass123!", "market")
    login(client, "sales1", "SalesPass123!")
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "sales1"


def test_change_password_success(client, db):
    make_user(db, "sales1", "OldPass123!", "market", must_change_password=True)
    r = login(client, "sales1", "OldPass123!")
    assert r.json()["must_change_password"] is True
    csrf = get_csrf(client)

    r2 = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "OldPass123!", "new_password": "NewPass456!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 200
    assert r2.json()["must_change_password"] is False

    # 旧密码失效
    assert login(client, "sales1", "OldPass123!").status_code == 401


def test_change_password_wrong_old(client, db):
    make_user(db, "sales1", "OldPass123!", "market")
    login(client, "sales1", "OldPass123!")
    csrf = get_csrf(client)
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrong-old", "new_password": "NewPass456!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 401


def test_change_password_requires_csrf(client, db):
    make_user(db, "sales1", "OldPass123!", "market")
    login(client, "sales1", "OldPass123!")
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "OldPass123!", "new_password": "NewPass456!"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_change_password_wrong_csrf(client, db):
    make_user(db, "sales1", "OldPass123!", "market")
    login(client, "sales1", "OldPass123!")
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "OldPass123!", "new_password": "NewPass456!"},
        headers={"X-CSRF-Token": "bogus-token"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_change_password_too_short(client, db):
    make_user(db, "sales1", "OldPass123!", "market")
    login(client, "sales1", "OldPass123!")
    csrf = get_csrf(client)
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "OldPass123!", "new_password": "short"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_me_reissues_csrf_when_missing(client, db):
    make_user(db, "sales1", "SalesPass123!", "market")
    login(client, "sales1", "SalesPass123!")
    assert "csrf_token" in client.cookies

    # 模拟 csrf cookie 丢失（如刷新后 token 缺失），仅保留会话 cookie
    client.cookies.delete("csrf_token")
    assert "csrf_token" not in client.cookies

    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert "csrf_token" in client.cookies


def test_logout_invalidates_session(client, db):
    make_user(db, "sales1", "SalesPass123!", "market")
    login(client, "sales1", "SalesPass123!")
    csrf = get_csrf(client)
    assert client.get("/api/v1/auth/me").status_code == 200

    lo = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert lo.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_error_response_shape(client, db):
    r = login(client, "nope", "x")
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "UNAUTHORIZED"
    assert body["message"]
    assert "request_id" in body
