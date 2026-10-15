"""Tests for approved YOLO checkpoint selection and provenance."""
from __future__ import annotations

import pytest

from app.integrations.model_registry import (
    YoloModelRegistryError,
    get_yolo_model,
    list_yolo_models,
)
from app.integrations.yolo_engine import YoloEngine


def test_registry_exposes_all_approved_checkpoints_with_sources() -> None:
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
        "seven_class_base_pre",
        "seven_class_asff_pre",
        "seven_class_dysample_pre",
        "four_class_obb",
        "coco80_base",
    }
    assert sum(item["is_default"] for item in metadata) == 1


def test_default_model_has_verified_provenance() -> None:
    spec = get_yolo_model()

    assert spec.key == "seven_class_asff"
    assert spec.current_sha256() == spec.expected_sha256
    assert spec.provenance_snapshot()["checkpoint"]["1"] == "Merchant"
    assert spec.provenance_snapshot()["canonical"]["1"] == "merchant"


def test_unknown_model_key_is_rejected() -> None:
    with pytest.raises(YoloModelRegistryError, match="Unknown YOLO model key"):
        get_yolo_model("../../untrusted.pt")


def test_obb_and_coco_models_are_selectable() -> None:
    obb_spec = get_yolo_model("four_class_obb")
    assert obb_spec.task == "obb"
    assert obb_spec.current_sha256() == obb_spec.expected_sha256

    coco_spec = get_yolo_model("coco80_base")
    assert coco_spec.task == "detect"
    assert len(coco_spec.canonical_class_names) == 80
    assert coco_spec.canonical_class_names[4] == "airplane"


def test_custom_model_provenance_includes_runtime_module_hash() -> None:
    spec = get_yolo_model("four_class_dysample")
    runtime_modules = spec.provenance_snapshot()["runtime_modules"]

    assert set(runtime_modules) == {"ultralytics.nn.modules.SCAM_DySample"}
    assert len(runtime_modules["ultralytics.nn.modules.SCAM_DySample"]) == 64


def test_seven_class_pre_models_are_selectable_and_distinct_from_main_set() -> None:
    """The '-pre' checkpoints live in a separate pt/7classes-pre/ folder and
    must be registered as distinct keys/fingerprints from pt/7classes/."""
    for pre_key, main_key in (
        ("seven_class_base_pre", "seven_class_base"),
        ("seven_class_asff_pre", "seven_class_asff"),
        ("seven_class_dysample_pre", "seven_class_dysample"),
    ):
        pre_spec = get_yolo_model(pre_key)
        main_spec = get_yolo_model(main_key)

        assert pre_spec.task == "detect"
        assert pre_spec.canonical_class_names == main_spec.canonical_class_names
        assert pre_spec.relative_path != main_spec.relative_path
        assert pre_spec.expected_sha256 != main_spec.expected_sha256
        assert pre_spec.current_sha256() == pre_spec.expected_sha256


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
    obb = None
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


class _Obb:
    xyxy = _TensorLike([[5.0, 6.0, 50.0, 60.0]])
    cls = _TensorLike([0.0])
    conf = _TensorLike([0.62])
    id = None


class _ObbResult:
    """Ultralytics leaves ``.boxes`` as ``None`` for OBB-task models and
    populates ``.obb`` instead."""

    boxes = None
    obb = _Obb()
    names = {0: "naval"}


def test_detection_output_supports_obb_models_via_axis_aligned_rectangle() -> None:
    engine = YoloEngine(model_key="four_class_obb")

    objects = engine._extract_objects(_ObbResult())

    assert objects == [
        {
            "object_index": 1,
            "class_id": 0,
            "class_name": "naval",
            "confidence": 0.62,
            "bbox": [5.0, 6.0, 50.0, 60.0],
        }
    ]


def test_detection_source_returns_none_when_neither_boxes_nor_obb_present() -> None:
    engine = YoloEngine(model_key="four_class_base")

    class _EmptyResult:
        boxes = None
        obb = None

    assert engine._extract_objects(_EmptyResult()) == []
