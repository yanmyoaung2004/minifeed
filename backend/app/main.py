import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.core.cache import set_feed
from app.core.config import DEFAULT_SECRET, settings
from app.db import models  # noqa: F401  register tables on Base.metadata
from app.db.database import Base, SessionLocal, engine
from app.routers import auth, posts
from app.routers.posts import load_posts, serialize_posts

logger = logging.getLogger("uvicorn.error")


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
    Base.metadata.create_all(bind=engine)
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

app.include_router(auth.router)
app.include_router(posts.router)