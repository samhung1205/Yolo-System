"""
Auth API routes:
  POST /api/auth/register
  POST /api/auth/login
  GET  /api/auth/me
  PUT  /api/auth/profile  (self-service: nickname / avatar / password)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import ProfileUpdate, UserCreate, UserRead, UserUpdate
from app.services.auth_service import login_user, register_user
from app.services import avatar_service, user_service
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
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Authenticate and receive a JWT access token."""
    # request.client is the direct peer; behind a reverse proxy configure
    # uvicorn --proxy-headers so this is the real client address.
    client_ip = request.client.host if request.client else None
    token, user = login_user(db, credentials.username, credentials.password, client_ip=client_ip)
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
    """Self-service profile update: nickname, avatar and/or password."""
    if profile_in.password is not None:
        if not profile_in.current_password or not verify_password(
            profile_in.current_password, current_user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="目前密碼不正確",
            )
    if profile_in.avatar is not None:
        avatar_service.check_avatar_assignment(
            db, acting_user_id=current_user.id, filename=profile_in.avatar, target_user=current_user
        )

    update_data = UserUpdate(
        nickname=profile_in.nickname,
        avatar=profile_in.avatar,
        password=profile_in.password,
    )
    updated = user_service.update_user(db, current_user.id, update_data)
    return to_user_read(updated)
