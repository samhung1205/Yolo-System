"""
Upload hardening helpers.

Stored uploads are later served back from ``/static`` with a media type
guessed from the file extension, so the extension must never come from the
client-supplied filename. Images get their extension from the decoded image
format (Pillow), and videos from a fixed allowlist. Anything else is refused.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Decoded Pillow format -> extension we store the file under.
IMAGE_FORMAT_EXTENSIONS: dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
    "BMP": ".bmp",
}

VIDEO_EXTENSIONS: set[str] = {".mp4", ".mov", ".avi", ".mkv", ".flv"}
VIDEO_CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "video/x-flv": ".flv",
}

# Media types /static is allowed to serve inline. Everything else is sent as
# an octet-stream attachment so a stray file can never render as a document.
STATIC_INLINE_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".flv": "video/x-flv",
    ".webm": "video/webm",
}


class InvalidUploadError(ValueError):
    """Raised when uploaded bytes are not an accepted media file."""


def _image_extension(image_source) -> str:
    # Ultralytics 8.4.38 replaces Image.open with a HEIF auto-install wrapper.
    # Reuse its saved Pillow function, including when YOLO was imported first.
    # Do not mutate the global decoder used by inference or install plugins.
    opener = Image.open
    if getattr(opener, "__module__", "") == "ultralytics.utils.patches":
        original = opener.__globals__.get("_image_open")
        if not callable(original) or getattr(original, "__module__", "") != "PIL.Image":
            raise RuntimeError("Unsupported Ultralytics Pillow wrapper")
        opener = original
    try:
        with opener(image_source, formats=tuple(IMAGE_FORMAT_EXTENSIONS)) as image:
            image_format = (image.format or "").upper()
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidUploadError("File is not a supported image") from exc

    extension = IMAGE_FORMAT_EXTENSIONS.get(image_format)
    if extension is None:
        raise InvalidUploadError("File is not a supported image")
    return extension


def image_extension_for_file(path: Path) -> str:
    """Return the storage extension for an image file on disk, or raise."""
    return _image_extension(path)


def image_extension_for_bytes(data: bytes) -> str:
    """Return the storage extension for in-memory image bytes, or raise."""
    return _image_extension(io.BytesIO(data))


def video_extension_for_upload(filename: str | None, content_type: str | None) -> str:
    """Pick a safe extension for a video upload, or raise.

    The client filename's extension is used only when it is on the allowlist;
    otherwise the declared content type must map to one.
    """
    extension = Path(filename or "").suffix.lower()
    if extension in VIDEO_EXTENSIONS:
        return extension
    mapped = VIDEO_CONTENT_TYPE_EXTENSIONS.get((content_type or "").lower())
    if mapped:
        return mapped
    raise InvalidUploadError("Only MP4, MOV, AVI, MKV, and FLV video uploads are supported")
