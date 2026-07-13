"""
Auth business logic: register and login.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def register_user(db: Session, user_in: UserCreate) -> User:
    """
    Register a new user.
    - Checks for duplicate username.
    - Hashes the password with bcrypt.
    - Persists and returns the new User.
    """
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="該帳號已存在，請重新註冊",
        )
    if user_in.email:
        existing_email = db.query(User).filter(User.email == user_in.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="該 Email 已存在，請使用其他 Email",
            )

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        nickname=user_in.nickname,
        is_admin=False,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def login_user(db: Session, username: str, password: str) -> tuple[str, User]:
    """
    Authenticate a user and return (jwt_token, user).
    Raises 401 if credentials are invalid.
    """
    account = username.strip()
    user = db.query(User).filter(
        or_(User.username == account, User.email == account),
        User.is_active == True,
    ).first()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
        )

    # Update last_login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(data={"sub": str(user.id)})
    return token, user
