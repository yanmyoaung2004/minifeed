from starlette.requests import Request

from app.core.rate_limit import user_id_key
from app.core.security import create_access_token


def _make_request(headers: dict | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": b"",
        "headers": raw,
        "client": ("203.0.113.7", 1234),
        "server": ("test", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_user_id_key_uses_token_subject():
    token = create_access_token("42")
    request = _make_request({"Authorization": f"Bearer {token}"})
    assert user_id_key(request) == "user:42"


def test_user_id_key_falls_back_to_ip_on_missing_token():
    request = _make_request({})
    assert user_id_key(request) == "203.0.113.7"


def test_user_id_key_falls_back_to_ip_on_bad_token():
    request = _make_request({"Authorization": "Bearer not-a-real-token"})
    assert user_id_key(request) == "203.0.113.7"


def test_user_id_key_falls_back_to_ip_on_malformed_header():
    request = _make_request({"Authorization": "garbage"})
    assert user_id_key(request) == "203.0.113.7"


def test_signup_rate_limited_per_ip(client):
    for i in range(5):
        resp = client.post(
            "/auth/signup",
            json={"username": f"user{i}", "email": f"user{i}@example.com", "password": "secret123"},
        )
        assert resp.status_code == 201

    resp = client.post(
        "/auth/signup",
        json={"username": "user5", "email": "user5@example.com", "password": "secret123"},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"].startswith("Rate limit exceeded: 5 per")
    assert resp.headers.get("Retry-After") is not None


def test_login_rate_limited_per_ip(client, make_user):
    make_user()
    for _ in range(4):
        resp = client.post(
            "/auth/login",
            json={"identifier": "yan@example.com", "password": "secret123"},
        )
        assert resp.status_code == 200

    resp = client.post(
        "/auth/login",
        json={"identifier": "yan@example.com", "password": "secret123"},
    )
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None


def test_create_post_limited_per_user_not_ip(client, make_user):
    headers = make_user(username="poster", email="poster@example.com")
    other = make_user(username="other", email="other@example.com")

    for _ in range(10):
        resp = client.post("/posts", json={"content": "spam"}, headers=headers)
        assert resp.status_code == 201

    resp = client.post("/posts", json={"content": "spam again"}, headers=headers)
    assert resp.status_code == 429
    assert resp.json()["detail"].startswith("Rate limit exceeded: 10 per")
    assert resp.headers.get("Retry-After") is not None

    other_resp = client.post("/posts", json={"content": "not limited"}, headers=other)
    assert other_resp.status_code == 201


def test_rate_limit_reset_between_tests(client, make_user):
    resp = client.post(
        "/auth/signup",
        json={"username": "fresh", "email": "fresh@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201