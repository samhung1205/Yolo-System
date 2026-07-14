"""Tests for approved YOLO checkpoint selection and provenance."""
from __future__ import annotations

import pytest

from app.integrations.model_registry import (
    YoloModelRegistryError,
    get_yolo_model,
    list_yolo_models,
)
from app.integrations.yolo_engine import YoloEngine


def test_registry_exposes_all_axis_aligned_checkpoints_with_sources() -> None:
    metadata = [spec.public_metadata() for spec in list_yolo_models()]
    available = [item for item in metadata if item["available"]]

    assert {item["key"] for item in available} == {
        "four_class_base",
        "four_class_asff",
        "four_class_dysample",
        "four_class_evmblock",
        "seven_class_base",
        "seven_class_asff",
        "seven_class_dysample",
    }
    assert sum(item["is_default"] for item in metadata) == 1


def test_default_model_has_verified_provenance() -> None:
    spec = get_yolo_model()

    assert spec.key == "seven_class_asff"
    assert spec.current_sha256() == spec.expected_sha256
    assert spec.provenance_snapshot()["checkpoint"]["1"] == "Merchant"
    assert spec.provenance_snapshot()["canonical"]["1"] == "merchant"


def test_unknown_and_obb_models_are_rejected() -> None:
    with pytest.raises(YoloModelRegistryError, match="Unknown YOLO model key"):
        get_yolo_model("../../untrusted.pt")

    with pytest.raises(YoloModelRegistryError, match="axis-aligned"):
        get_yolo_model("four_class_obb")


def test_custom_model_provenance_includes_runtime_module_hash() -> None:
    spec = get_yolo_model("four_class_dysample")
    runtime_modules = spec.provenance_snapshot()["runtime_modules"]

    assert set(runtime_modules) == {"ultralytics.nn.modules.SCAM_DySample"}
    assert len(runtime_modules["ultralytics.nn.modules.SCAM_DySample"]) == 64


class _TensorLike:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class _Boxes:
    xyxy = _TensorLike([[1.0, 2.0, 30.0, 40.0]])
    cls = _TensorLike([1.0])
    conf = _TensorLike([0.875])
    id = None


class _Result:
    boxes = _Boxes()
    names = {1: "Merchant"}


def test_detection_output_uses_canonical_class_name() -> None:
    engine = YoloEngine(model_key="four_class_base")

    objects = engine._extract_objects(_Result())

    assert objects == [
        {
            "object_index": 1,
            "class_id": 1,
            "class_name": "merchant",
            "confidence": 0.875,
            "bbox": [1.0, 2.0, 30.0, 40.0],
        }
    ]
