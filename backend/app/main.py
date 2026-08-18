import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import DEFAULT_SECRET, settings
from app.db import models  # noqa: F401  register tables on Base.metadata
from app.db.database import Base, engine
from app.routers import auth

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.SECRET_KEY == DEFAULT_SECRET:
        logger.warning(
            "SECRET_KEY is the insecure default. Set it in .env for anything beyond local development."
        )
    Base.metadata.create_all(bind=engine)
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