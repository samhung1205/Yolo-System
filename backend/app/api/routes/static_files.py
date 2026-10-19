"""
Protected static asset delivery.

Assets are no longer served anonymously. Clients must either:
1. Use a short-lived signed URL (`?sig=...&exp=...`) returned by API responses, or
2. Send `Authorization: Bearer <jwt>` for programmatic downloads.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, resolve_user_from_token
from app.core.static_tokens import verify_static_signature
from app.core.uploads import STATIC_INLINE_MEDIA_TYPES
from app.models.user import User
from app.services.static_access_service import resolve_static_file, user_can_access_static_path

router = APIRouter(tags=["Static"])

# Static assets are user-uploaded media. Even if a non-media file ever lands
# under static/, it must not render as a document on this origin: browsers
# must not sniff it, and a direct navigation runs in a script-less sandbox.
STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; sandbox",
}


@router.get("/static/{file_path:path}")
def serve_static_file(
    file_path: str,
    db: Annotated[Session, Depends(get_db)],
    sig: Annotated[Optional[str], Query()] = None,
    exp: Annotated[Optional[int], Query()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
):
    relative_path = file_path.replace("\\", "/")

    if sig is not None and exp is not None:
        if not verify_static_signature(relative_path, sig, exp):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired static asset signature",
            )
    else:
        current_user = _get_user_from_authorization(db, authorization)
        if not user_can_access_static_path(db, current_user=current_user, relative_path=relative_path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this static asset",
            )

    full_path = resolve_static_file(relative_path)
    media_type = STATIC_INLINE_MEDIA_TYPES.get(full_path.suffix.lower())
    if media_type is None:
        return FileResponse(
            full_path,
            media_type="application/octet-stream",
            filename=full_path.name,
            headers=STATIC_SECURITY_HEADERS,
        )
    return FileResponse(full_path, media_type=media_type, headers=STATIC_SECURITY_HEADERS)


def _get_user_from_authorization(db: Session, authorization: Optional[str]) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for static asset access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    user = resolve_user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
