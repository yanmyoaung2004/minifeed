import json
from hashlib import sha256
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from starlette.concurrency import run_in_threadpool

from app.core.cache import get_feed, invalidate_feed, set_feed
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter, user_id_key
from app.db.database import get_db
from app.db.models import Post, User
from app.schemas.post import PostCreate, PostOut

router = APIRouter(prefix="/posts", tags=["posts"])

FEED_CACHE_CONTROL = "public, max-age=30"
WARNING_STALE = '110 - "Response is stale"'


def load_posts(db: Session) -> list[Post]:
    stmt = (
        select(Post)
        .options(joinedload(Post.author))
        .order_by(Post.created_at.desc())
    )
    return list(db.scalars(stmt))


def serialize_posts(posts: list[Post]) -> str:
    payload = [PostOut.model_validate(p).model_dump(mode="json") for p in posts]
    return json.dumps(payload, separators=(",", ":"))


def feed_etag(payload: str) -> str:
    return '"' + sha256(payload.encode()).hexdigest() + '"'


def _cache_headers(cache_status: str, etag: str, stale: bool = False) -> dict:
    headers = {
        "X-Cache": cache_status,
        "Cache-Control": FEED_CACHE_CONTROL,
        "ETag": etag,
    }
    if stale:
        headers["Warning"] = WARNING_STALE
    return headers


@router.get("", response_class=Response)
async def list_posts(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    cached, fresh = await get_feed()
    if cached is not None and fresh:
        etag = feed_etag(cached)
        headers = _cache_headers("HIT", etag)
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
        return Response(content=cached, media_type="application/json", headers=headers)

    try:
        posts = await run_in_threadpool(load_posts, db)
    except Exception:
        if cached is not None:
            etag = feed_etag(cached)
            headers = _cache_headers("STALE", etag, stale=True)
            if request.headers.get("if-none-match") == etag:
                return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
            return Response(content=cached, media_type="application/json", headers=headers)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        )

    payload = serialize_posts(posts)
    await set_feed(payload)
    etag = feed_etag(payload)
    headers = _cache_headers("MISS", etag)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=payload, media_type="application/json", headers=headers)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PostOut)
@limiter.limit("10/minute", key_func=user_id_key)
async def create_post(
    request: Request,
    payload: PostCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Post:
    def _create() -> Post:
        post = Post(content=payload.content, user_id=current_user.id, author=current_user)
        db.add(post)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(post)
        return post

    try:
        post = await run_in_threadpool(_create)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="could not create post",
        )
    await invalidate_feed()
    return post