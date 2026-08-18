import logging
import re
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.oauth import (
    build_authorize_url,
    create_state,
    exchange_code,
    fetch_userinfo,
    get_configured_providers,
    verify_state,
)
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import User

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


def _login_error(error: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.FRONTEND_URL}/login?error={error}", status_code=302)


def _login_success(user_id: int) -> RedirectResponse:
    token = create_access_token(subject=str(user_id))
    return RedirectResponse(f"{settings.FRONTEND_URL}?token={token}", status_code=302)


def _sanitize_username(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", value or "").lower()[:20]
    cleaned = cleaned or "user"
    while len(cleaned) < 3:
        cleaned += "0"
    return cleaned


def _dedupe_username(db: Session, base: str) -> str:
    candidate = _sanitize_username(base)
    existing = db.execute(
        select(User).where(func.lower(User.username) == candidate.lower()).limit(1)
    ).scalar_one_or_none()
    if existing is None:
        return candidate
    for i in range(2, 100):
        alt = f"{candidate[:16]}{i}"
        taken = db.execute(
            select(User).where(func.lower(User.username) == alt.lower()).limit(1)
        ).scalar_one_or_none()
        if taken is None:
            return alt
    return f"{candidate[:12]}{secrets.token_hex(3)}"


def _resolve_user(db: Session, provider: str, profile: dict) -> User:
    email = (profile.get("email") or "").strip().lower()
    oauth_id = str(profile.get("id") or profile.get("sub") or "")
    name = profile.get("name") or profile.get("login") or ""
    if not email:
        email = f"{oauth_id}@{provider}.oauth.local"
    if not oauth_id:
        raise ValueError("oauth profile missing identity")

    user = None
    if email:
        user = db.execute(
            select(User).where(User.email == email).limit(1)
        ).scalar_one_or_none()

    if user is None:
        user = User(
            username=_dedupe_username(db, name or email.split("@")[0]),
            email=email,
            hashed_password=None,
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(user)
    else:
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            db.add(user)
            db.commit()
            db.refresh(user)
    return user


@router.get("/providers")
def oauth_providers() -> dict:
    return {"providers": get_configured_providers()}


@router.get("/{provider}")
async def oauth_authorize(provider: str) -> RedirectResponse:
    if provider not in get_configured_providers():
        return _login_error("not_configured")
    state = create_state(provider)
    url = await build_authorize_url(provider, state)
    return RedirectResponse(url, status_code=302)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    db: Annotated[Session, Depends(get_db)],
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    if error is not None:
        return _login_error("denied")
    if provider not in get_configured_providers():
        return _login_error("not_configured")
    if not state or not verify_state(state, provider):
        return _login_error("invalid")
    if not code:
        return _login_error("invalid")
    try:
        token_data = await exchange_code(provider, code)
        profile = await fetch_userinfo(provider, token_data["access_token"])
    except Exception:
        logger.warning("OAuth callback failed for provider %s", provider, exc_info=True)
        return _login_error("invalid")
    try:
        user = _resolve_user(db, provider, profile)
    except Exception:
        logger.warning("OAuth account resolution failed for provider %s", provider, exc_info=True)
        return _login_error("invalid")
    return _login_success(user.id)