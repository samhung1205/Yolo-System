"""Tests for per-class confidence / IoU threshold detection.

Two layers are covered:

* ``parse_class_thresholds`` request validation (pure, always runs).
* The engine's per-class filtering, checked against real Ultralytics output.
  Those tests are skipped when ultralytics/torch or the registered checkpoint
  is unavailable, so the suite still runs in a bare environment.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.integrations.yolo_engine import ClassThreshold, _apply_per_class_thresholds
from app.services.detection_service import (
    _class_thresholds_from_json,
    _class_thresholds_to_json,
    parse_class_thresholds,
)

MODEL_KEY = "seven_class_base"


# --------------------------------------------------------------------------
# Request validation
# --------------------------------------------------------------------------
@pytest.fixture
def model_spec():
    registry = pytest.importorskip("app.integrations.model_registry")
    try:
        return registry.get_yolo_model(MODEL_KEY)
    except registry.YoloModelRegistryError as exc:  # pragma: no cover
        pytest.skip(f"model {MODEL_KEY} unavailable: {exc}")


@pytest.mark.parametrize("raw", [None, "", "   ", "{}"])
def test_blank_payload_falls_back_to_scalar_thresholds(raw, model_spec):
    assert parse_class_thresholds(raw, model_spec) is None


def test_valid_payload_is_parsed(model_spec):
    parsed = parse_class_thresholds(
        '{"0": {"conf": 0.2, "iou": 0.4}, "4": {"conf": 0.5, "iou": 0.35}}',
        model_spec,
    )
    assert parsed == {
        0: ClassThreshold(conf=0.2, iou=0.4),
        4: ClassThreshold(conf=0.5, iou=0.35),
    }


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '"a string"',
        '{"abc": {"conf": 0.2, "iou": 0.4}}',
        '{"0": {"conf": 1.5, "iou": 0.4}}',
        '{"0": {"conf": -0.1, "iou": 0.4}}',
        '{"0": {"conf": 0.2}}',
        '{"0": {"iou": 0.4}}',
        '{"0": "not-an-object"}',
    ],
)
def test_malformed_payload_is_rejected(raw, model_spec):
    with pytest.raises(HTTPException) as exc_info:
        parse_class_thresholds(raw, model_spec)
    assert exc_info.value.status_code == 400


def test_class_id_outside_the_model_is_rejected(model_spec):
    unknown_id = max(model_spec.canonical_class_names) + 50
    with pytest.raises(HTTPException) as exc_info:
        parse_class_thresholds(f'{{"{unknown_id}": {{"conf": 0.2, "iou": 0.4}}}}', model_spec)
    assert exc_info.value.status_code == 400
    assert str(unknown_id) in exc_info.value.detail


def test_json_round_trip_preserves_thresholds():
    thresholds = {0: ClassThreshold(conf=0.2, iou=0.4), 4: ClassThreshold(conf=0.5, iou=0.35)}
    payload = _class_thresholds_to_json(thresholds)
    assert payload == {"0": {"conf": 0.2, "iou": 0.4}, "4": {"conf": 0.5, "iou": 0.35}}
    assert _class_thresholds_from_json(payload) == thresholds


def test_empty_thresholds_serialize_to_none():
    assert _class_thresholds_to_json(None) is None
    assert _class_thresholds_to_json({}) is None
    assert _class_thresholds_from_json(None) is None
    assert _class_thresholds_from_json({}) is None


# --------------------------------------------------------------------------
# Engine behaviour against real Ultralytics output
# --------------------------------------------------------------------------
def _sample_images(limit=3):
    root = Path("static/detections/originals")
    suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return [p for p in sorted(root.glob("*")) if p.suffix.lower() in suffixes][:limit]


@pytest.fixture(scope="module")
def loaded_model():
    pytest.importorskip("ultralytics")
    pytest.importorskip("torchvision")
    from app.integrations.model_registry import YoloModelRegistryError, get_yolo_model

    try:
        spec = get_yolo_model(MODEL_KEY)
    except YoloModelRegistryError as exc:  # pragma: no cover
        pytest.skip(f"model {MODEL_KEY} unavailable: {exc}")
    if not spec.checkpoint_path.exists():  # pragma: no cover
        pytest.skip("checkpoint file missing")

    from ultralytics import YOLO

    return YOLO(str(spec.checkpoint_path)), spec


@pytest.fixture(scope="module")
def images():
    found = _sample_images()
    if not found:  # pragma: no cover
        pytest.skip("no sample images available under static/detections/originals")
    return found


def _rows(result, ndigits=2):
    """Comparable, order-independent view of a result's boxes."""
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []
    return sorted(
        tuple(round(float(v), ndigits) for v in row) for row in boxes.data.detach().cpu()
    )


def test_per_class_conf_matches_running_that_class_directly(loaded_model, images):
    """A high per-class conf must give the same boxes as predicting at that conf.

    This is the property that makes post-filtering exact: greedy NMS walks
    boxes in descending confidence, so extra low-confidence candidates can
    never displace a box above the threshold.
    """
    model, spec = loaded_model
    low, high = 0.20, 0.50

    for image in images:
        direct = model.predict(source=str(image), conf=high, iou=0.45,
                               imgsz=spec.input_size, verbose=False)[0]

        widened = model.predict(source=str(image), conf=low, iou=1.0,
                                imgsz=spec.input_size, max_det=3000, verbose=False)[0]
        _apply_per_class_thresholds(
            widened,
            default_conf=high,
            default_iou=0.45,
            class_thresholds={},
            max_det=3000,
        )

        assert _rows(widened) == _rows(direct), f"mismatch on {image.name}"


def test_per_class_iou_reproduces_ultralytics_nms(loaded_model, images):
    """Re-running NMS per class at the same IoU must match Ultralytics itself.

    Ultralytics' default NMS is already class-aware, so this confirms our
    replacement suppression is equivalent rather than merely similar.
    """
    model, spec = loaded_model
    conf, iou = 0.20, 0.45

    for image in images:
        reference = model.predict(source=str(image), conf=conf, iou=iou,
                                  imgsz=spec.input_size, verbose=False)[0]

        widened = model.predict(source=str(image), conf=conf, iou=1.0,
                                imgsz=spec.input_size, max_det=3000, verbose=False)[0]
        assert len(widened.boxes) >= len(reference.boxes), (
            "disabling NMS should never yield fewer candidates"
        )
        _apply_per_class_thresholds(
            widened,
            default_conf=conf,
            default_iou=iou,
            class_thresholds={cid: ClassThreshold(conf=conf, iou=iou)
                              for cid in spec.canonical_class_names},
            max_det=3000,
        )

        assert _rows(widened) == _rows(reference), f"mismatch on {image.name}"


def test_raising_one_class_conf_only_affects_that_class(loaded_model, images):
    """Per-class thresholds must not leak across classes."""
    model, spec = loaded_model
    conf, iou = 0.20, 0.45

    for image in images:
        baseline = model.predict(source=str(image), conf=conf, iou=iou,
                                 imgsz=spec.input_size, verbose=False)[0]
        baseline_rows = baseline.boxes.data.detach().cpu()
        if len(baseline_rows) == 0:
            continue

        # Pick a class that is actually present, then make it unreachable.
        target = int(baseline_rows[0][-1])
        widened = model.predict(source=str(image), conf=conf, iou=1.0,
                                imgsz=spec.input_size, max_det=3000, verbose=False)[0]
        _apply_per_class_thresholds(
            widened,
            default_conf=conf,
            default_iou=iou,
            class_thresholds={target: ClassThreshold(conf=1.0, iou=iou)},
            max_det=3000,
        )

        kept = widened.boxes.data.detach().cpu()
        assert all(int(row[-1]) != target for row in kept), "suppressed class still present"

        expected_others = sorted(
            tuple(round(float(v), 2) for v in row)
            for row in baseline_rows
            if int(row[-1]) != target
        )
        actual_others = sorted(tuple(round(float(v), 2) for v in row) for row in kept)
        assert actual_others == expected_others, f"other classes changed on {image.name}"


def test_output_stays_sorted_by_confidence(loaded_model, images):
    """Grouping by class must not disturb Ultralytics' output ordering."""
    model, spec = loaded_model

    for image in images:
        widened = model.predict(source=str(image), conf=0.2, iou=1.0,
                                imgsz=spec.input_size, max_det=3000, verbose=False)[0]
        _apply_per_class_thresholds(
            widened,
            default_conf=0.2,
            default_iou=0.45,
            class_thresholds={0: ClassThreshold(conf=0.3, iou=0.5)},
            max_det=3000,
        )
        confidences = [float(row[-2]) for row in widened.boxes.data.detach().cpu()]
        assert confidences == sorted(confidences, reverse=True)
