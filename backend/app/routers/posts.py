from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Post, User
from app.schemas.post import PostCreate, PostOut

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostOut])
def list_posts(db: Annotated[Session, Depends(get_db)]) -> list[Post]:
    stmt = (
        select(Post)
        .options(joinedload(Post.author))
        .order_by(Post.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Post:
    post = Post(content=payload.content, user_id=current_user.id, author=current_user)
    db.add(post)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="could not create post",
        )
    db.refresh(post)
    return post