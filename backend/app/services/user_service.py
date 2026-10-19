"""
User CRUD business logic — used by admin routes.
"""
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.detection_task import DetectionTask
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services import avatar_service

STATIC_ROOT = Path("static")


def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在")
    return user


def list_users(
    db: Session,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
) -> dict:
    query = db.query(User)
    if search:
        query = query.filter(
            User.username.contains(search) | User.nickname.contains(search) | User.email.contains(search)
        )
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "page": page, "limit": limit, "items": items}


def create_user_by_admin(db: Session, user_in: UserCreate, is_admin: bool = False) -> User:
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="該帳號已存在",
        )
    if user_in.email:
        existing_email = db.query(User).filter(User.email == user_in.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="該 Email 已存在",
            )
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        nickname=user_in.nickname,
        avatar=user_in.avatar,
        is_admin=is_admin,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def guard_admin_change(
    db: Session,
    *,
    acting_user: User,
    target_user_id: int,
    user_in: Optional[UserUpdate] = None,
    deleting: bool = False,
) -> None:
    """Refuse changes that would lock administrators out.

    An admin may not delete, demote or deactivate their own account, and the
    last active admin cannot be removed by anyone.
    """
    target = get_user_by_id(db, target_user_id)
    removes_admin = deleting or (
        user_in is not None
        and ((user_in.is_admin is False) or (user_in.is_active is False))
    )
    if not removes_admin or not target.is_admin:
        return
    if target.id == acting_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能刪除、停用或移除自己的管理員權限",
        )
    other_admins = (
        db.query(User)
        .filter(User.is_admin == True, User.is_active == True, User.id != target.id)
        .count()
    )
    if other_admins == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系統至少需要保留一位啟用中的管理員",
        )


def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User:
    user = get_user_by_id(db, user_id)

    if user_in.username and user_in.username != user.username:
        conflict = db.query(User).filter(User.username == user_in.username).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="帳號已存在，請使用其他帳號",
            )
        user.username = user_in.username

    if user_in.email is not None and user_in.email != user.email:
        conflict = db.query(User).filter(User.email == user_in.email).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email 已存在，請使用其他 Email",
            )
        user.email = user_in.email

    if user_in.nickname is not None:
        user.nickname = user_in.nickname

    previous_avatar = user.avatar
    if user_in.avatar is not None:
        user.avatar = user_in.avatar

    revoke_tokens = False
    if user_in.password is not None:
        user.password_hash = hash_password(user_in.password)
        revoke_tokens = True

    if user_in.is_admin is not None and user_in.is_admin != user.is_admin:
        user.is_admin = user_in.is_admin
        revoke_tokens = True

    if user_in.is_active is not None and user_in.is_active != user.is_active:
        user.is_active = user_in.is_active
        revoke_tokens = True

    if revoke_tokens:
        # Every token issued before this change stops working (deps.resolve_user_from_token).
        user.token_version = (user.token_version or 0) + 1

    db.commit()
    db.refresh(user)
    if previous_avatar and previous_avatar != user.avatar:
        avatar_service.delete_if_unreferenced(db, previous_avatar)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user_by_id(db, user_id)

    # Collect static file paths BEFORE the delete cascades the DB rows away,
    # so detection media and the avatar don't become orphaned on disk.
    file_paths = _collect_user_static_files(db, user)
    avatar = user.avatar

    db.delete(user)
    db.commit()

    # The avatar goes only if no other account uses it; unassigned uploads by
    # this user go regardless of age.
    avatar_service.delete_if_unreferenced(db, avatar)
    avatar_service.prune_pending_uploads(db, user_id, older_than_seconds=0)

    for path in file_paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            # File cleanup must never fail the API call; leftover files can
            # be removed manually if the filesystem is temporarily unhappy.
            pass


def _collect_user_static_files(db: Session, user: User) -> list[Path]:
    paths: list[Path] = []
    tasks = db.query(DetectionTask).filter(DetectionTask.user_id == user.id).all()
    for task in tasks:
        for relative in (
            task.source_image_path,
            task.result_image_path,
            task.source_video_path,
            task.result_video_path,
            task.preview_image_path,
        ):
            if relative:
                paths.append(STATIC_ROOT / relative)
    return paths
