import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

FEED_KEY = "feed:v1"
FEED_TS_KEY = "feed:v1:ts"
STALE_RETENTION_SECONDS = 86400

_client: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
    return _client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_feed() -> tuple[str | None, bool]:
    """Return (cached_payload, is_fresh). (None, False) when nothing is cached."""
    try:
        data, ts = await _get_client().mget(FEED_KEY, FEED_TS_KEY)
    except Exception:
        logger.warning("Redis unavailable; bypassing cache", exc_info=True)
        return None, False
    if data is None:
        return None, False
    fresh = False
    if ts is not None:
        try:
            written = datetime.fromisoformat(ts)
            fresh = (datetime.now(timezone.utc) - written).total_seconds() <= settings.FEED_CACHE_TTL
        except ValueError:
            fresh = False
    return data, fresh


async def set_feed(payload_json: str) -> bool:
    try:
        client = _get_client()
        async with client.pipeline(transaction=True) as pipe:
            pipe.set(FEED_KEY, payload_json, ex=STALE_RETENTION_SECONDS)
            pipe.set(FEED_TS_KEY, _now_iso(), ex=STALE_RETENTION_SECONDS)
            await pipe.execute()
        return True
    except Exception:
        logger.warning("Failed to write feed cache", exc_info=True)
        return False


async def invalidate_feed() -> bool:
    try:
        await _get_client().delete(FEED_KEY, FEED_TS_KEY)
        return True
    except Exception:
        logger.warning("Failed to invalidate feed cache", exc_info=True)
        return False