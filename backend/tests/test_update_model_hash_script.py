"""Tests for scripts/update_model_hash.py — the tool that re-pins checkpoint
SHA-256 fingerprints in model_registry.py after a checkpoint file is swapped.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_model_hash.py"
_spec = importlib.util.spec_from_file_location("update_model_hash", _SCRIPT_PATH)
update_model_hash = importlib.util.module_from_spec(_spec)
sys.modules["update_model_hash"] = update_model_hash
_spec.loader.exec_module(update_model_hash)


def test_actual_sha256_matches_hashlib(tmp_path):
    path = tmp_path / "checkpoint.pt"
    path.write_bytes(b"some-fake-checkpoint-bytes")

    import hashlib

    expected = hashlib.sha256(b"some-fake-checkpoint-bytes").hexdigest()
    assert update_model_hash._actual_sha256(path) == expected


def test_update_registry_source_only_touches_target_key(tmp_path):
    registry_file = tmp_path / "model_registry.py"
    registry_file.write_text(
        "SPECS = (\n"
        "    YoloModelSpec(\n"
        '        key="model_a",\n'
        '        expected_sha256="1111111111111111111111111111111111111111111111111111111111111111",\n'
        "    ),\n"
        "    YoloModelSpec(\n"
        '        key="model_b",\n'
        '        expected_sha256="2222222222222222222222222222222222222222222222222222222222222222",\n'
        "    ),\n"
        ")\n",
        encoding="utf-8",
    )

    new_hash = "a" * 64
    update_model_hash._update_registry_source("model_a", new_hash, registry_file=registry_file)

    updated = registry_file.read_text(encoding="utf-8")
    assert f'expected_sha256="{new_hash}"' in updated
    # model_b's fingerprint must be untouched
    assert '2222222222222222222222222222222222222222222222222222222222222222' in updated
    assert updated.count("expected_sha256=") == 2


def test_update_registry_source_raises_when_key_missing(tmp_path):
    registry_file = tmp_path / "model_registry.py"
    registry_file.write_text(
        'YoloModelSpec(key="model_a", expected_sha256="' + "1" * 64 + '")\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="could not find"):
        update_model_hash._update_registry_source("missing_key", "a" * 64, registry_file=registry_file)


def _fake_spec(**overrides):
    defaults = dict(
        key="fake_model",
        checkpoint_path=Path("/nonexistent/fake.pt"),
        expected_sha256="0" * 64,
        task="detect",
        checkpoint_class_names={0: "a"},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_process_model_reports_missing_file():
    spec = _fake_spec(checkpoint_path=Path("/definitely/does/not/exist.pt"))
    assert update_model_hash.process_model(spec, dry_run=True) == "missing"


def test_process_model_unchanged_when_hash_matches(tmp_path):
    path = tmp_path / "checkpoint.pt"
    path.write_bytes(b"same-bytes")
    actual = update_model_hash._actual_sha256(path)
    spec = _fake_spec(checkpoint_path=path, expected_sha256=actual)

    assert update_model_hash.process_model(spec, dry_run=True) == "unchanged"


def test_process_model_skips_when_validation_fails(tmp_path, monkeypatch):
    path = tmp_path / "checkpoint.pt"
    path.write_bytes(b"new-bytes-that-differ")
    spec = _fake_spec(checkpoint_path=path, expected_sha256="f" * 64)

    monkeypatch.setattr(
        update_model_hash, "_validate_checkpoint", lambda _spec: (False, "class mapping mismatch")
    )

    assert update_model_hash.process_model(spec, dry_run=True) == "skipped"


def test_process_model_dry_run_does_not_write(tmp_path, monkeypatch):
    path = tmp_path / "checkpoint.pt"
    path.write_bytes(b"new-bytes-that-differ")
    spec = _fake_spec(checkpoint_path=path, expected_sha256="f" * 64)

    monkeypatch.setattr(update_model_hash, "_validate_checkpoint", lambda _spec: (True, "ok"))

    called = False

    def _fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(update_model_hash, "_update_registry_source", _fail_if_called)

    assert update_model_hash.process_model(spec, dry_run=True) == "updated"
    assert called is False
