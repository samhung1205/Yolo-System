"""
Upload hardening: stored extensions come from decoded content, and /static
never renders an unexpected file type as a document.
"""
import io
from pathlib import Path
import types

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.core.static_tokens import build_signed_static_url
from app.core.uploads import (
    InvalidUploadError,
    image_extension_for_bytes,
    video_extension_for_upload,
)
from app.services import detection_service, static_access_service
from main import app

HTML_PAYLOAD = b"<html><script>alert(document.domain)</script></html>"


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(name: str, data: bytes, content_type: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name, headers={"content-type": content_type})


@pytest.fixture
def static_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "static"
    originals = root / "detections" / "originals"
    originals.mkdir(parents=True)
    monkeypatch.setattr(detection_service, "_static_root", lambda: root)
    monkeypatch.setattr(settings, "DETECTION_SOURCE_DIR", str(originals))
    monkeypatch.setattr(static_access_service, "STATIC_ROOT", root)
    return root


def test_image_extension_comes_from_decoded_format():
    assert image_extension_for_bytes(_png_bytes()) == ".png"


def test_polyglot_png_with_html_tail_is_still_stored_as_png():
    assert image_extension_for_bytes(_png_bytes() + HTML_PAYLOAD) == ".png"


def test_non_image_bytes_are_rejected():
    with pytest.raises(InvalidUploadError):
        image_extension_for_bytes(HTML_PAYLOAD)


@pytest.fixture
def heif_autoinstall_wrapper(monkeypatch):
    """Reproduce the 8.4.38 wrapper without importing YOLO or using the network."""
    native = Image.open
    if getattr(native, "__module__", "") == "ultralytics.utils.patches":
        native = native.__globals__["_image_open"]
    module = types.ModuleType("ultralytics.utils.patches")
    module._image_open = native
    module.install_attempts = []
    exec('''def image_open(source, *args, **kwargs):
    try:
        return _image_open(source, *args, **kwargs)
    except Exception:
        install_attempts.append("pi-heif")
        raise ModuleNotFoundError("No module named pi_heif", name="pi_heif")
''', module.__dict__)
    monkeypatch.setattr(Image, "open", module.image_open)
    return module


def test_invalid_upload_is_rejected_without_heif_import_or_install(heif_autoinstall_wrapper):
    # First prove this is the same failure mode observed in the offline image.
    with pytest.raises(ModuleNotFoundError):
        Image.open(io.BytesIO(HTML_PAYLOAD))
    heif_autoinstall_wrapper.install_attempts.clear()
    with pytest.raises(InvalidUploadError):
        image_extension_for_bytes(HTML_PAYLOAD)
    assert heif_autoinstall_wrapper.install_attempts == []
    assert Image.open is heif_autoinstall_wrapper.image_open


@pytest.mark.parametrize("format, extension", [("JPEG", ".jpg"), ("PNG", ".png"),
    ("WEBP", ".webp"), ("GIF", ".gif"), ("BMP", ".bmp")])
def test_supported_images_still_decode_after_yolo_patch(heif_autoinstall_wrapper, format, extension):
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(stream, format=format)
    assert image_extension_for_bytes(stream.getvalue()) == extension
    assert heif_autoinstall_wrapper.install_attempts == []


def test_disallowed_tiff_does_not_enable_an_extra_decoder(heif_autoinstall_wrapper):
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(stream, format="TIFF")
    with pytest.raises(InvalidUploadError):
        image_extension_for_bytes(stream.getvalue())
    assert heif_autoinstall_wrapper.install_attempts == []


def test_invalid_upload_cleans_staging_file_after_yolo_patch(static_root, heif_autoinstall_wrapper):
    with pytest.raises(HTTPException) as exc_info:
        detection_service._store_original_image(8, _upload("evil.png", HTML_PAYLOAD, "image/png"))
    assert exc_info.value.status_code == 400
    assert list((static_root / "detections" / "originals").iterdir()) == []
    assert heif_autoinstall_wrapper.install_attempts == []


@pytest.mark.parametrize(
    ("filename", "content_type", "expected"),
    [
        ("clip.MOV", None, ".mov"),
        ("evil.html", "video/mp4", ".mp4"),
        ("no_extension", "video/x-matroska", ".mkv"),
    ],
)
def test_video_extension_never_trusts_unknown_filename_suffix(filename, content_type, expected):
    assert video_extension_for_upload(filename, content_type) == expected


def test_video_with_unknown_extension_and_type_is_rejected():
    with pytest.raises(InvalidUploadError):
        video_extension_for_upload("evil.html", "text/html")


def test_store_original_image_ignores_client_extension(static_root):
    full_path, relative_path = detection_service._store_original_image(
        7, _upload("evil.html", _png_bytes(), "image/png")
    )
    assert full_path.suffix == ".png"
    assert relative_path.endswith(".png")
    assert list(full_path.parent.iterdir()) == [full_path]


def test_store_original_image_rejects_non_image_and_cleans_up(static_root):
    with pytest.raises(HTTPException) as exc_info:
        detection_service._store_original_image(8, _upload("evil.png", HTML_PAYLOAD, "image/png"))
    assert exc_info.value.status_code == 400
    assert list((static_root / "detections" / "originals").iterdir()) == []


def test_static_serves_unknown_types_as_download_with_security_headers(static_root):
    (static_root / "detections" / "originals" / "legacy.html").write_bytes(HTML_PAYLOAD)
    client = TestClient(app)

    response = client.get(build_signed_static_url("detections/originals/legacy.html"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in response.headers["content-security-policy"]


def test_static_serves_images_inline(static_root):
    (static_root / "detections" / "originals" / "ok.png").write_bytes(_png_bytes())
    client = TestClient(app)

    response = client.get(build_signed_static_url("detections/originals/ok.png"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "content-disposition" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_api_responses_carry_nosniff():
    response = TestClient(app).get("/api/agent/modes")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
