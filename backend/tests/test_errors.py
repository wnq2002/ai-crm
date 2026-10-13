"""统一错误信封与 request_id 注入测试（api-contract §1）。"""

from app.services import auth_service


def test_validation_error_envelope(client, db):
    # 缺 password 且 username 为空 → 422
    r = client.post("/api/v1/auth/login", json={"username": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"]
    assert body["request_id"]
    assert "errors" in body["details"]


def test_internal_error_envelope(client_factory, db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(auth_service, "login", boom)
    # raise_server_exceptions=False：让 app 的 Exception 处理器产出信封而非向测试抛出
    c = client_factory(raise_server_exceptions=False)
    r = c.post("/api/v1/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "INTERNAL"
    assert body["message"]
    assert body["request_id"]
