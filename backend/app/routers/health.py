from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.cache import _get_client
from app.db.database import SessionLocal

router = APIRouter(tags=["health"])


def _check_db() -> bool:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return True
    except Exception:
        return False


async def _check_cache() -> bool:
    try:
        await _get_client().ping()
        return True
    except Exception:
        return False


@router.get("/health")
async def health() -> JSONResponse:
    db_ok = _check_db()
    cache_ok = await _check_cache()
    ok = db_ok and cache_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "healthy" if ok else "degraded",
            "database": "ok" if db_ok else "error",
            "cache": "ok" if cache_ok else "error",
        },
    )