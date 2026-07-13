"""
Tests for signed static URL helpers.
"""
from app.core.static_tokens import (
    build_signed_static_url,
    normalize_static_relative_path,
    verify_static_signature,
)


def test_normalize_static_relative_path_strips_prefix():
    assert normalize_static_relative_path("/static/avatars/a.jpg") == "avatars/a.jpg"
    assert normalize_static_relative_path("detections/results/task_1.jpg") == "detections/results/task_1.jpg"


def test_build_and_verify_signed_static_url():
    signed = build_signed_static_url("detections/results/task_1.jpg")
    assert signed.startswith("/static/detections/results/task_1.jpg?")
    assert "sig=" in signed
    assert "exp=" in signed

    relative = "detections/results/task_1.jpg"
    query = signed.split("?", 1)[1]
    params = dict(part.split("=", 1) for part in query.split("&"))
    assert verify_static_signature(relative, params["sig"], int(params["exp"])) is True


def test_verify_static_signature_rejects_tampered_path():
    signed = build_signed_static_url("avatars/demo.jpg")
    query = signed.split("?", 1)[1]
    params = dict(part.split("=", 1) for part in query.split("&"))
    assert verify_static_signature("avatars/other.jpg", params["sig"], int(params["exp"])) is False
