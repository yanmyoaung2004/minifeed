from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def signup(
    request: Request,
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing = db.execute(
        select(User).where(
            or_(
                User.email == payload.email,
                func.lower(User.username) == payload.username.lower(),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        detail = "email already registered" if existing.email == payload.email else "username already taken"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email or username already registered",
        )
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    identifier = payload.identifier.strip().lower()
    user = db.execute(
        select(User)
        .where(or_(User.email == identifier, func.lower(User.username) == identifier))
        .limit(1)
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return Token(access_token=create_access_token(subject=str(user.id)))


@router.get("/me", response_model=UserOut)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user