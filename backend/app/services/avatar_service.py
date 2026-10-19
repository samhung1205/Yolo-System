"""
Avatar files: who uploaded them, who may use them, and when they are deleted.

Uploads are named ``u{uploader_id}_{YYYYmmddHHMMSS}_{hex8}.{ext}``, so the
uploader is known without an extra table. A user may only assign an avatar
they uploaded themselves (admins too: they upload, then assign it to the
account they are editing), and never one that another account already uses.

Files nothing references any more are removed:
- the previous avatar, right after an account switches to a new one;
- an uploader's unassigned uploads older than ``PENDING_UPLOAD_TTL_SECONDS``,
  on that uploader's next upload;
- a deleted account's avatar and unassigned uploads.

``scripts/cleanup_avatars.py`` sweeps the whole directory, including files
named before this scheme (``YYYYmmddHHMMSS_hex8.ext``).
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

AVATAR_DIR = Path("static/avatars")
PENDING_UPLOAD_TTL_SECONDS = 3600

AVATAR_FILENAME_RE = re.compile(r"^u(?P<uploader>\d+)_\d{14}_[0-9a-f]{8}\.(jpg|png|gif|webp)$")

INVALID_AVATAR_MESSAGE = "頭像檔案無效，請重新上傳頭像"
MISSING_AVATAR_MESSAGE = "找不到上傳的頭像，請重新上傳"
AVATAR_IN_USE_MESSAGE = "此頭像已被其他帳號使用，請重新上傳頭像"


def new_avatar_filename(uploader_id: int, ext: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"u{uploader_id}_{timestamp}_{uuid.uuid4().hex[:8]}{ext}"


def uploader_of(filename: str) -> Optional[int]:
    match = AVATAR_FILENAME_RE.match(filename or "")
    return int(match.group("uploader")) if match else None


def is_plain_filename(name: Optional[str]) -> bool:
    """A bare file name inside AVATAR_DIR (no directories, no dotfiles)."""
    return bool(name) and "/" not in name and "\\" not in name and not name.startswith(".")


def is_referenced(db: Session, filename: str, *, exclude_user_id: Optional[int] = None) -> bool:
    query = db.query(User.id).filter(User.avatar == filename)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None


def check_avatar_assignment(
    db: Session,
    *,
    acting_user_id: int,
    filename: str,
    target_user: Optional[User] = None,
) -> None:
    """Raise 400 unless ``acting_user_id`` may set ``filename`` on ``target_user``.

    ``target_user`` is None when an admin creates a new account. Re-sending the
    account's current avatar is always allowed (clients echo it back).
    """
    if target_user is not None and filename == target_user.avatar:
        return
    if uploader_of(filename) != acting_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_AVATAR_MESSAGE)
    if not (AVATAR_DIR / filename).is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MISSING_AVATAR_MESSAGE)
    exclude = target_user.id if target_user is not None else None
    if is_referenced(db, filename, exclude_user_id=exclude):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=AVATAR_IN_USE_MESSAGE)


def unlink_quietly(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        # Cleanup must never fail the request; the sweep script catches leftovers.
        logger.warning("Could not delete avatar file %s", path.name)
        return False


def delete_if_unreferenced(db: Session, filename: Optional[str]) -> bool:
    if not is_plain_filename(filename) or is_referenced(db, filename):
        return False
    return unlink_quietly(AVATAR_DIR / filename)


def prune_pending_uploads(
    db: Session,
    uploader_id: int,
    *,
    older_than_seconds: float = PENDING_UPLOAD_TTL_SECONDS,
    keep: Optional[str] = None,
    now: Optional[float] = None,
) -> list[str]:
    """Delete ``uploader_id``'s uploads that no account uses and are old enough."""
    if not AVATAR_DIR.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - older_than_seconds
    removed: list[str] = []
    for path in AVATAR_DIR.glob(f"u{uploader_id}_*"):
        name = path.name
        if name == keep or uploader_of(name) != uploader_id or not path.is_file():
            continue
        if path.stat().st_mtime > cutoff or is_referenced(db, name):
            continue
        if unlink_quietly(path):
            removed.append(name)
    return removed


def find_orphans(
    db: Session,
    *,
    older_than_seconds: float = PENDING_UPLOAD_TTL_SECONDS,
    now: Optional[float] = None,
) -> list[Path]:
    """Every avatar file no account uses, older than ``older_than_seconds``."""
    if not AVATAR_DIR.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - older_than_seconds
    referenced = {
        name for (name,) in db.query(User.avatar).filter(User.avatar.isnot(None)).all() if name
    }
    return sorted(
        path
        for path in AVATAR_DIR.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.name not in referenced
        and path.stat().st_mtime <= cutoff
    )
