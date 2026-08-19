import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.concurrency import run_in_threadpool

from app.core.cache import set_feed
from app.core.config import DEFAULT_SECRET, settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db import models  # noqa: F401  register tables on Base.metadata
from app.db.database import Base, SessionLocal, engine
from app.routers import auth, health, oauth, posts
from app.routers.posts import load_posts, serialize_posts

logger = logging.getLogger("uvicorn.error")


def _init_schema_with_retry(retries: int = 10, delay: float = 2.0) -> None:
    for attempt in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception:
            if attempt == retries - 1:
                raise
            logger.warning(
                "Database not ready (attempt %s/%s); retrying", attempt + 1, retries
            )
            time.sleep(delay)


async def _warm_feed_cache() -> None:
    def _load() -> list:
        db = SessionLocal()
        try:
            return load_posts(db)
        finally:
            db.close()

    try:
        posts_list = await run_in_threadpool(_load)
        await set_feed(serialize_posts(posts_list))
    except Exception:
        logger.warning("Feed pre-warm failed; continuing without warm cache", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.SECRET_KEY == DEFAULT_SECRET:
        logger.warning(
            "SECRET_KEY is the insecure default. Set it in .env for anything beyond local development."
        )
    _init_schema_with_retry()
    await _warm_feed_cache()
    yield


app = FastAPI(title="MiniFeed API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(posts.router)
app.include_router(health.router)