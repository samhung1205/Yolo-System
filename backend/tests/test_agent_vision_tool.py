"""Tests for the agent's read-only detection image loader (vision support)."""
from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from app.agents.tools import detection_tools


def _user(user_id=1, is_admin=False):
    return SimpleNamespace(id=user_id, is_admin=is_admin)


def _task(**overrides):
    defaults = dict(
        id=1,
        user_id=1,
        result_image_path=None,
        preview_image_path=None,
        source_image_path=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_load_detection_image_tool_prefers_result_image(tmp_path, monkeypatch):
    monkeypatch.setattr(detection_tools, "_STATIC_ROOT", tmp_path)
    image_path = tmp_path / "detections" / "results" / "task_1.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    image_path.write_bytes(image_bytes)

    task = _task(
        result_image_path="detections/results/task_1.jpg",
        source_image_path="detections/originals/task_1.jpg",
    )
    monkeypatch.setattr(detection_tools.detection_repository, "get_task", lambda db, task_id: task)

    result = detection_tools.load_detection_image_tool(None, current_user=_user(), detection_id=1)

    assert result["ok"] is True
    assert result["path_used"] == "detections/results/task_1.jpg"
    assert result["is_annotated"] is True
    assert result["mime_type"] == "image/jpeg"
    assert base64.b64decode(result["image_base64"]) == image_bytes


def test_load_detection_image_tool_denies_other_users_task(monkeypatch):
    task = _task(user_id=2, result_image_path="detections/results/task_1.jpg")
    monkeypatch.setattr(detection_tools.detection_repository, "get_task", lambda db, task_id: task)

    result = detection_tools.load_detection_image_tool(None, current_user=_user(user_id=1), detection_id=1)

    assert result["ok"] is False
    assert "not allowed" in result["error"]


def test_load_detection_image_tool_missing_file_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(detection_tools, "_STATIC_ROOT", tmp_path)
    task = _task(result_image_path="detections/results/missing.jpg")
    monkeypatch.setattr(detection_tools.detection_repository, "get_task", lambda db, task_id: task)

    result = detection_tools.load_detection_image_tool(None, current_user=_user(), detection_id=1)

    assert result["ok"] is False
    assert "not found" in result["error"]


def test_load_detection_image_tool_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(detection_tools, "_STATIC_ROOT", tmp_path)
    task = _task(result_image_path="../outside.jpg")
    monkeypatch.setattr(detection_tools.detection_repository, "get_task", lambda db, task_id: task)

    result = detection_tools.load_detection_image_tool(None, current_user=_user(), detection_id=1)

    assert result["ok"] is False


def test_load_detection_image_tool_enforces_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(detection_tools, "_STATIC_ROOT", tmp_path)
    monkeypatch.setattr(detection_tools.settings, "AGENT_VISION_MAX_IMAGE_BYTES", 4)
    image_path = tmp_path / "detections" / "results" / "task_1.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"way-too-large-for-the-limit")

    task = _task(result_image_path="detections/results/task_1.jpg")
    monkeypatch.setattr(detection_tools.detection_repository, "get_task", lambda db, task_id: task)

    result = detection_tools.load_detection_image_tool(None, current_user=_user(), detection_id=1)

    assert result["ok"] is False
    assert "size limit" in result["error"]
