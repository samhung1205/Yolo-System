"""
Signed URL helpers for protected static assets.

`<img>` and plain `<a download>` cannot send Authorization headers, so API
responses embed short-lived HMAC signatures in `/static/...` query params.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.core.config import settings

_SIGNATURE_VERSION = "v1"


def normalize_static_relative_path(path: str) -> str:
    """Normalize a path relative to the `static/` root."""
    if not path or not str(path).strip():
        raise ValueError("Static path is required")

    normalized = str(path).strip().replace("\\", "/")
    while normalized.startswith("/"):
        normalized = normalized[1:]
    if normalized.startswith("static/"):
        normalized = normalized[len("static/") :]

    if not normalized or ".." in normalized.split("/"):
        raise ValueError("Invalid static path")

    return normalized


def _compute_signature(relative_path: str, expires_at: int) -> str:
    payload = f"{_SIGNATURE_VERSION}:{relative_path}:{expires_at}"
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def build_signed_static_url(path: str) -> str:
    """Return `/static/...` with `sig` and `exp` query params."""
    relative_path = normalize_static_relative_path(path)
    expires_at = int(time.time()) + settings.STATIC_URL_EXPIRE_SECONDS
    signature = _compute_signature(relative_path, expires_at)
    query = urlencode({"sig": signature, "exp": expires_at})
    return f"/static/{relative_path}?{query}"


def verify_static_signature(relative_path: str, signature: str, expires_at: int) -> bool:
    """Validate a signed static URL."""
    if not signature or expires_at <= 0:
        return False
    if int(time.time()) > int(expires_at):
        return False

    try:
        normalized = normalize_static_relative_path(relative_path)
    except ValueError:
        return False

    expected = _compute_signature(normalized, int(expires_at))
    return hmac.compare_digest(expected, signature)
