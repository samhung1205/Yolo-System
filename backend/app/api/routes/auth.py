"""
Auth API routes:
  POST /api/auth/register
  POST /api/auth/login
  GET  /api/auth/me
  PUT  /api/auth/profile  (self-service: nickname / password)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import ProfileUpdate, UserCreate, UserRead, UserUpdate
from app.services.auth_service import login_user, register_user
from app.services import user_service
from app.services.user_response_service import to_user_read

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """Register a new user account."""
    user = register_user(db, user_in)
    return to_user_read(user)


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Authenticate and receive a JWT access token."""
    token, user = login_user(db, credentials.username, credentials.password)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=to_user_read(user),
    )


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return the currently authenticated user's profile."""
    return to_user_read(current_user)


@router.put("/profile", response_model=UserRead)
def update_my_profile(
    profile_in: ProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Self-service profile update: change nickname and/or password."""
    update_data = UserUpdate(
        nickname=profile_in.nickname,
        password=profile_in.password,
    )
    updated = user_service.update_user(db, current_user.id, update_data)
    return to_user_read(updated)
