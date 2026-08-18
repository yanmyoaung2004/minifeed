import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.security import decode_access_token

logger = logging.getLogger("uvicorn.error")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    headers_enabled=False,
    swallow_errors=True,
    in_memory_fallback_enabled=True,
    enabled=True,
)


def user_id_key(request: Request) -> str:
    """Rate-limit by authenticated user id; falls back to the client IP."""
    try:
        auth = request.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() == "bearer" and token:
            subject = decode_access_token(token)
            return f"user:{subject}"
    except Exception:
        logger.warning("Rate-limit key resolution failed; falling back to IP", exc_info=True)
    return get_remote_address(request)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    try:
        retry_after = int(exc.limit.limit.get_expiry())
    except Exception:
        retry_after = 60
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": str(retry_after)},
    )