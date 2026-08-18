import jwt

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.models import User


def signup(client, username="yan", email="yan@example.com", password="secret123"):
    return client.post(
        "/auth/signup",
        json={"username": username, "email": email, "password": password},
    )


def login(client, identifier, password):
    return client.post(
        "/auth/login",
        json={"identifier": identifier, "password": password},
    )


def test_signup_success(client):
    resp = signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "yan"
    assert body["email"] == "yan@example.com"
    assert "id" in body
    assert "created_at" in body
    assert "hashed_password" not in body


def test_signup_email_normalized_to_lowercase(client):
    resp = signup(client, email="  YAN@Example.COM  ")
    assert resp.status_code == 201
    assert resp.json()["email"] == "yan@example.com"


def test_signup_duplicate_email(client):
    signup(client)
    resp = signup(client, username="other", email="yan@example.com")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "email already registered"


def test_signup_duplicate_username(client):
    signup(client)
    resp = signup(client, email="other@example.com")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "username already taken"


def test_signup_invalid_email(client):
    resp = signup(client, email="not-an-email")
    assert resp.status_code == 422


def test_signup_short_password(client):
    resp = signup(client, password="123")
    assert resp.status_code == 422


def test_signup_short_username(client):
    resp = signup(client, username="ab")
    assert resp.status_code == 422


def test_signup_whitespace_username(client):
    resp = signup(client, username="   ")
    assert resp.status_code == 422


def test_signup_username_case_variant_duplicate(client):
    assert signup(client, username="TestUser", email="a@example.com").status_code == 201
    resp = signup(client, username="testuser", email="b@example.com")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "username already taken"


def test_login_with_legacy_case_duplicates_never_500(client, db_session):
    session = db_session()
    session.add_all(
        [
            User(username="TestUser", email="a@example.com", hashed_password="x"),
            User(username="testuser", email="b@example.com", hashed_password="x"),
        ]
    )
    session.commit()

    resp = client.post(
        "/auth/login",
        json={"identifier": "testuser", "password": "secret123"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid credentials"}


def test_login_success_by_email(client):
    signup(client)
    resp = login(client, "yan@example.com", "secret123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    payload = jwt.decode(body["access_token"], settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "1"
    assert "exp" in payload


def test_login_success_by_username_case_insensitive(client):
    signup(client)
    resp = login(client, "YAN", "secret123")
    assert resp.status_code == 200


def test_login_wrong_password(client):
    signup(client)
    resp = login(client, "yan@example.com", "wrongpass")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_nonexistent_user(client):
    resp = login(client, "ghost@example.com", "whatever1")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_no_user_enumeration(client):
    signup(client)
    wrong_pw = login(client, "yan@example.com", "wrongpass")
    missing = login(client, "ghost@example.com", "whatever1")
    assert wrong_pw.status_code == 401
    assert wrong_pw.json() == missing.json()


def test_login_malformed_body(client):
    resp = client.post("/auth/login", json={"identifier": ""})
    assert resp.status_code == 422


def test_me_requires_auth(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "yan"
    assert body["email"] == "yan@example.com"
    assert "hashed_password" not in body