"""
File upload routes:
  POST /api/upload/avatar
"""
import os
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.deps import get_current_user
from app.core.static_tokens import build_signed_static_url
from app.models.user import User

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
AVATAR_DIR = "static/avatars"


@router.post("/avatar")
async def upload_avatar(
    file: Annotated[UploadFile, File(description="Avatar image (JPEG/PNG, max 5MB)")],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Upload an avatar image. Returns the saved filename."""
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

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(AVATAR_DIR, filename)

    os.makedirs(AVATAR_DIR, exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(contents)

    return {
        "filename": filename,
        "url": build_signed_static_url(f"avatars/{filename}"),
    }
