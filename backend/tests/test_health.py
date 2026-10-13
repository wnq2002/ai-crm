"""健康检查与 request_id 透传。"""


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_request_id_echo(client):
    r = client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    assert r.headers.get("X-Request-Id") == "abc-123"


def test_request_id_generated(client):
    r = client.get("/healthz")
    assert r.headers.get("X-Request-Id")
