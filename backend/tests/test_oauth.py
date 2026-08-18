import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from app.core.config import settings
from app.core.oauth import create_state
from app.core.security import ALGORITHM
from app.db.models import User


@pytest.fixture()
def oauth_creds(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "gh-test-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "gh-test-secret")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "goog-test-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "goog-test-secret")
    monkeypatch.setattr("app.core.oauth._registered", set())
    return None


async def _fake_exchange(provider, code):
    return {"access_token": "fake-access-token"}


async def _fake_github_userinfo(provider, access_token):
    return {"id": 123, "login": "john", "name": "John Doe", "email": "John@Example.COM"}


def _state_param(location: str) -> str:
    return parse_qs(urlparse(location).query)["state"][0]


def _token_from_redirect(location: str) -> str:
    return parse_qs(urlparse(location).query)["token"][0]


def test_providers_empty_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", None)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", None)
    monkeypatch.setattr("app.core.oauth._registered", set())
    resp = client.get("/auth/oauth/providers")
    assert resp.status_code == 200
    assert resp.json() == {"providers": []}


def test_providers_listed_when_configured(client, oauth_creds):
    resp = client.get("/auth/oauth/providers")
    assert resp.status_code == 200
    assert resp.json() == {"providers": ["github", "google"]}


def test_authorize_redirects_with_signed_state(client, oauth_creds):
    resp = client.get("/auth/oauth/github", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize")
    state = _state_param(location)
    from app.core.oauth import verify_state

    assert verify_state(state, "github") is True


def test_authorize_unconfigured_provider_redirects(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", None)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", None)
    monkeypatch.setattr("app.core.oauth._registered", set())
    resp = client.get("/auth/oauth/github", follow_redirects=False)
    assert resp.status_code == 302
    assert "error=not_configured" in resp.headers["location"]


def test_callback_creates_new_user(client, oauth_creds, monkeypatch, db_session):
    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_github_userinfo)

    state = create_state("github")
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(settings.FRONTEND_URL)
    assert "error=" not in location

    token = _token_from_redirect(location)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    user = db_session().get(User, int(payload["sub"]))
    assert user is not None
    assert user.email == "john@example.com"
    assert user.username == "johndoe"
    assert user.hashed_password is None
    assert user.oauth_provider == "github"
    assert user.oauth_id == "123"


def test_callback_merges_existing_email(client, oauth_creds, monkeypatch, db_session):
    resp = client.post(
        "/auth/signup",
        json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    existing_id = resp.json()["id"]

    async def _fake_userinfo(provider, access_token):
        return {"id": 999, "login": "bob-github", "name": "Bob", "email": "Bob@Example.COM"}

    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_userinfo)

    state = create_state("github")
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    token = _token_from_redirect(resp.headers["location"])
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert int(payload["sub"]) == existing_id

    user = db_session().get(User, existing_id)
    assert user.oauth_provider == "github"
    assert user.oauth_id == "999"
    assert user.hashed_password is not None


def test_callback_username_dedupe(client, oauth_creds, monkeypatch, db_session):
    client.post(
        "/auth/signup",
        json={"username": "johndoe", "email": "other@example.com", "password": "secret123"},
    )
    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_github_userinfo)

    state = create_state("github")
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    token = _token_from_redirect(resp.headers["location"])
    user = db_session().get(User, int(jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]))
    assert user.username == "johndoe2"


def test_callback_tampered_state_rejected(client, oauth_creds, monkeypatch):
    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_github_userinfo)

    state = create_state("github")
    tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={tampered}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=invalid" in resp.headers["location"]


def test_callback_expired_state_rejected(client, oauth_creds, monkeypatch):
    payload = json.dumps(
        {"nonce": "x", "provider": "github", "exp": int(time.time()) - 10},
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(
        settings.SECRET_KEY.encode(), payload, hashlib.sha256
    ).hexdigest()
    expired = base64.urlsafe_b64encode(payload).decode() + "." + signature

    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_github_userinfo)
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={expired}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=invalid" in resp.headers["location"]


def test_callback_state_provider_mismatch(client, oauth_creds, monkeypatch):
    state = create_state("github")
    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_github_userinfo)
    resp = client.get(
        f"/auth/oauth/google/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert "error=invalid" in resp.headers["location"]


def test_callback_missing_code(client, oauth_creds):
    state = create_state("github")
    resp = client.get(
        f"/auth/oauth/github/callback?state={state}",
        follow_redirects=False,
    )
    assert "error=invalid" in resp.headers["location"]


def test_callback_user_cancellation(client, oauth_creds):
    resp = client.get(
        "/auth/oauth/github/callback?error=access_denied&error_description=denied",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=denied" in resp.headers["location"]


def test_callback_exchange_failure_redirects(client, oauth_creds, monkeypatch):
    async def _boom(provider, code):
        raise RuntimeError("token exchange failed")

    monkeypatch.setattr("app.routers.oauth.exchange_code", _boom)
    state = create_state("github")
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=invalid" in resp.headers["location"]


def test_oauth_user_password_login_rejected(client, oauth_creds, monkeypatch):
    monkeypatch.setattr("app.routers.oauth.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.routers.oauth.fetch_userinfo", _fake_github_userinfo)

    state = create_state("github")
    resp = client.get(
        f"/auth/oauth/github/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert "error=" not in resp.headers["location"]

    login = client.post(
        "/auth/login",
        json={"identifier": "john@example.com", "password": "anything123"},
    )
    assert login.status_code == 401
    assert login.json() == {"detail": "Invalid credentials"}