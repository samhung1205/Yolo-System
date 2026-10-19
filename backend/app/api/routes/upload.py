"""
File upload routes:
  POST /api/upload/avatar
"""
import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.static_tokens import build_signed_static_url
from app.core.uploads import InvalidUploadError, image_extension_for_bytes
from app.models.user import User
from app.services import avatar_service

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/avatar")
async def upload_avatar(
    file: Annotated[UploadFile, File(description="Avatar image (JPEG/PNG, max 5MB)")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Upload an avatar image. Returns the saved filename.

    The file is named after the uploader (avatar_service), so only this user
    can later assign it; their older unassigned uploads are pruned here.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支援 JPEG、PNG、GIF、WEBP 格式",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="檔案大小不可超過 5MB",
        )

    # The stored extension comes from the decoded image format, never the
    # client filename, because /static serves files by extension.
    try:
        ext = image_extension_for_bytes(contents)
    except InvalidUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支援 JPEG、PNG、GIF、WEBP 格式",
        ) from exc
    if ext == ".bmp":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支援 JPEG、PNG、GIF、WEBP 格式",
        )
    filename = avatar_service.new_avatar_filename(current_user.id, ext)
    avatar_dir = avatar_service.AVATAR_DIR
    os.makedirs(avatar_dir, exist_ok=True)
    with open(avatar_dir / filename, "wb") as f:
        f.write(contents)

    avatar_service.prune_pending_uploads(db, current_user.id, keep=filename)

    return {
        "filename": filename,
        "url": build_signed_static_url(f"avatars/{filename}"),
    }
