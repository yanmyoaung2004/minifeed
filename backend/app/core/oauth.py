import base64
import hashlib
import hmac
import json
import secrets
import time

import httpx
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings

STATE_TTL_SECONDS = 600

oauth = OAuth()

PROVIDER_META = {
    "github": {
        "userinfo_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scope": "user:email",
    },
    "google": {
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
}

_registered: set[str] = set()


def _provider_credentials(name: str) -> tuple[str, str] | None:
    if name == "github":
        if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
            return settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET
    elif name == "google":
        if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
            return settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    return None


def _ensure_registered(name: str) -> None:
    if name in _registered:
        return
    credentials = _provider_credentials(name)
    if credentials is None:
        return
    client_id, client_secret = credentials
    if name == "github":
        oauth.register(
            name="github",
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://github.com/login/oauth/authorize",
            access_token_url="https://github.com/login/oauth/access_token",
        )
    elif name == "google":
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            access_token_url="https://oauth2.googleapis.com/token",
        )
    _registered.add(name)


def get_configured_providers() -> list[str]:
    providers = []
    for name in ("github", "google"):
        if _provider_credentials(name) is not None:
            _ensure_registered(name)
            providers.append(name)
    return providers


def get_client(name: str):
    _ensure_registered(name)
    return oauth.create_client(name)


def redirect_uri_for(provider: str) -> str:
    return f"{settings.OAUTH_CALLBACK_BASE}/auth/oauth/{provider}/callback"


def create_state(provider: str) -> str:
    payload = json.dumps(
        {
            "nonce": secrets.token_urlsafe(16),
            "provider": provider,
            "exp": int(time.time()) + STATE_TTL_SECONDS,
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode() + "." + signature


def verify_state(state: str, provider: str) -> bool:
    try:
        body, signature = state.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(body.encode())
        expected = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False
        data = json.loads(payload)
        if data.get("provider") != provider:
            return False
        if int(data.get("exp", 0)) < int(time.time()):
            return False
        return True
    except Exception:
        return False


async def build_authorize_url(provider: str, state: str) -> str:
    client = get_client(provider)
    result = await client.create_authorization_url(
        redirect_uri=redirect_uri_for(provider),
        scope=PROVIDER_META[provider]["scope"],
        state=state,
    )
    return result["url"]


async def exchange_code(provider: str, code: str) -> dict:
    client = get_client(provider)
    return await client.fetch_access_token(
        redirect_uri=redirect_uri_for(provider),
        code=code,
    )


async def fetch_userinfo(provider: str, access_token: str) -> dict:
    client = get_client(provider)
    meta = PROVIDER_META[provider]
    resp = await client.request("GET", meta["userinfo_url"], token=access_token)
    resp.raise_for_status()
    data = resp.json()
    if provider == "github" and not data.get("email"):
        emails = await _fetch_github_emails(client, access_token)
        if emails:
            primary = next((e for e in emails if e.get("primary")), emails[0])
            data["email"] = primary.get("email")
    return data


async def _fetch_github_emails(client, access_token: str) -> list[dict]:
    resp = await client.request(
        "GET",
        PROVIDER_META["github"]["emails_url"],
        token=access_token,
    )
    resp.raise_for_status()
    return resp.json()