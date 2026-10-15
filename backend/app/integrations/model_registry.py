"""Approved YOLO checkpoint registry and provenance helpers.

Only checkpoints declared here can be selected by API clients.  The browser
never supplies a filesystem path, which prevents arbitrary checkpoint loading.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import file_digest
from pathlib import Path

from app.core.config import settings
from app.integrations.legacy_checkpoint_compat import (
    legacy_source_fingerprints,
    legacy_source_status,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

FOUR_CLASS_CHECKPOINT = {
    0: "naval",
    1: "Merchant",
    2: "dock",
    3: "other_vessel",
}
FOUR_CLASS_CANONICAL = {
    0: "naval",
    1: "merchant",
    2: "dock",
    3: "other_vessel",
}
SEVEN_CLASS_CHECKPOINT = {
    **FOUR_CLASS_CHECKPOINT,
    4: "airplane",
    5: "large-vehicle",
    6: "small-vehicle",
}
SEVEN_CLASS_CANONICAL = {
    **FOUR_CLASS_CANONICAL,
    4: "airplane",
    5: "large-vehicle",
    6: "small-vehicle",
}

# Standard COCO-80 class names, as embedded in the official Ultralytics
# ``yolo11n.pt`` checkpoint. This is a stock/official model (not part of the
# custom maritime dataset), so canonical names are identical to checkpoint
# names — no relabeling needed.
COCO80_CLASS_NAMES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite",
    34: "baseball bat", 35: "baseball glove", 36: "skateboard",
    37: "surfboard", 38: "tennis racket", 39: "bottle", 40: "wine glass",
    41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl",
    46: "banana", 47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli",
    51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut", 55: "cake",
    56: "chair", 57: "couch", 58: "potted plant", 59: "bed",
    60: "dining table", 61: "toilet", 62: "tv", 63: "laptop", 64: "mouse",
    65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
    69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
    74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear",
    78: "hair drier", 79: "toothbrush",
}


class YoloModelRegistryError(ValueError):
    """Raised when a requested checkpoint is unknown or unavailable."""


@dataclass(frozen=True)
class YoloModelSpec:
    key: str
    display_name: str
    relative_path: str
    architecture: str
    dataset_variant: str
    expected_sha256: str
    checkpoint_class_names: dict[int, str]
    canonical_class_names: dict[int, str]
    input_size: int = 960
    task: str = "detect"
    selectable: bool = True
    disabled_reason: str | None = None

    @property
    def checkpoint_path(self) -> Path:
        return (_BACKEND_ROOT / self.relative_path).resolve()

    def current_sha256(self) -> str | None:
        path = self.checkpoint_path
        if not path.is_file():
            return None
        stat = path.stat()
        return _sha256_for_file(str(path), stat.st_size, stat.st_mtime_ns)

    def availability(self) -> tuple[bool, str | None]:
        if not self.selectable:
            return False, self.disabled_reason or "This checkpoint is not enabled for inference."
        if not self.checkpoint_path.is_file():
            return False, "Checkpoint file is missing."
        digest = self.current_sha256()
        if digest != self.expected_sha256:
            return False, "Checkpoint fingerprint changed; registry review is required."
        sources_available, reason = legacy_source_status(self.key)
        if not sources_available:
            return False, reason
        return True, None

    def provenance_snapshot(self) -> dict[str, dict[str, str]]:
        snapshot = {
            "checkpoint": {str(key): value for key, value in self.checkpoint_class_names.items()},
            "canonical": {str(key): value for key, value in self.canonical_class_names.items()},
        }
        runtime_modules = legacy_source_fingerprints(self.key)
        if runtime_modules:
            snapshot["runtime_modules"] = runtime_modules
        return snapshot

    def public_metadata(self) -> dict:
        available, reason = self.availability()
        return {
            "key": self.key,
            "display_name": self.display_name,
            "checkpoint": self.relative_path,
            "architecture": self.architecture,
            "dataset_variant": self.dataset_variant,
            "task": self.task,
            "input_size": self.input_size,
            "checkpoint_class_names": self.checkpoint_class_names,
            "canonical_class_names": self.canonical_class_names,
            "class_count": len(self.canonical_class_names),
            "sha256": self.current_sha256(),
            "available": available,
            "is_default": self.key == settings.YOLO_DEFAULT_MODEL_KEY,
            "unavailable_reason": reason,
        }


@lru_cache(maxsize=32)
def _sha256_for_file(path: str, _size: int, _mtime_ns: int) -> str:
    with Path(path).open("rb") as checkpoint:
        return file_digest(checkpoint, "sha256").hexdigest()


_MODEL_SPECS = (
    YoloModelSpec(
        key="four_class_base",
        display_name="YOLO11n Base (4 classes)",
        relative_path="pt/4classes/yolo11n_base.pt",
        architecture="YOLO11n Base",
        dataset_variant="4-class maritime",
        expected_sha256="b147d7e43a5a7ef0538be1e1a7150de9f88ee0623af8b4df3897a30a22c6c35d",
        checkpoint_class_names=FOUR_CLASS_CHECKPOINT,
        canonical_class_names=FOUR_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="four_class_asff",
        display_name="YOLO11n + ASFF (4 classes)",
        relative_path="pt/4classes/yolo11n_asff.pt",
        architecture="YOLO11n + ASFF",
        dataset_variant="4-class maritime",
        expected_sha256="b4e2414650e1c659224231bb9907390b1edd753fb99f2c9c3b0e99e55cbf6904",
        checkpoint_class_names=FOUR_CLASS_CHECKPOINT,
        canonical_class_names=FOUR_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_base",
        display_name="YOLO11n Base (7 classes)",
        relative_path="pt/7classes/yolo11n_base.pt",
        architecture="YOLO11n Base",
        dataset_variant="7-class multimodal",
        expected_sha256="cc07f186d823ff9bf390c9adc37f822665b99b4cab41d271ac79b011e818019e",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_asff",
        display_name="YOLO11n + ASFF (7 classes)",
        relative_path="pt/7classes/yolo11n_asff.pt",
        architecture="YOLO11n + ASFF",
        dataset_variant="7-class multimodal",
        expected_sha256="5b4a9b1ff1b0ed94bb2039ee0651812c8cd57e735f07f21dd304124c418a6131",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="four_class_dysample",
        display_name="YOLO11n + DySample (4 classes)",
        relative_path="pt/4classes/yolo11n_dysample.pt",
        architecture="YOLO11n + DySample",
        dataset_variant="4-class maritime",
        expected_sha256="5585146589104ec6b2207e8353432df7159a2cade6279401627061eca5f2fcfc",
        checkpoint_class_names=FOUR_CLASS_CHECKPOINT,
        canonical_class_names=FOUR_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="four_class_evmblock",
        display_name="YOLO11n + EfficientViM (4 classes)",
        relative_path="pt/4classes/yolo11n_evmblock.pt",
        architecture="YOLO11n + EfficientViM",
        dataset_variant="4-class maritime",
        expected_sha256="213768fd62ec04215973a260aac7f150db62d41f6e06f843ca616ab6748b72f7",
        checkpoint_class_names=FOUR_CLASS_CHECKPOINT,
        canonical_class_names=FOUR_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_dysample",
        display_name="YOLO11n + DySample (7 classes)",
        relative_path="pt/7classes/yolo11n_dysample.pt",
        architecture="YOLO11n + DySample",
        dataset_variant="7-class multimodal",
        expected_sha256="108f96ac81665135582404b623ac1abaf0bf63f173ba608287a26bbd2b2cc63a",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_base_pre",
        display_name="YOLO11n Base (7 classes, Pre)",
        relative_path="pt/7classes-pre/yolo11n_base.pt",
        architecture="YOLO11n Base",
        dataset_variant="7-class multimodal (pre)",
        expected_sha256="f243cf4adc1bc63e1b0ae44a3d650056d362e08ebe9b810155ed0f379982621c",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_asff_pre",
        display_name="YOLO11n + ASFF (7 classes, Pre)",
        relative_path="pt/7classes-pre/yolo11n_asff.pt",
        architecture="YOLO11n + ASFF",
        dataset_variant="7-class multimodal (pre)",
        expected_sha256="e92fed6757bf8732da3ae2d35d9900f4c77515b19704011412ed90ad4cbc6dff",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_dysample_pre",
        display_name="YOLO11n + DySample (7 classes, Pre)",
        relative_path="pt/7classes-pre/yolo11n_dysample.pt",
        architecture="YOLO11n + DySample",
        dataset_variant="7-class multimodal (pre)",
        expected_sha256="c2ce1acbb73bea8c3ef35ce527a8b2ef2631894023cd6a132a606ae938eccf8a",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="four_class_obb",
        display_name="YOLO11n OBB (4 classes)",
        relative_path="pt/yolo11n_obb.pt",
        architecture="YOLO11n OBB",
        dataset_variant="4-class maritime",
        expected_sha256="51994b8eb702274bd09a178e3e1ce85f2be75c534c540ce5045c863e34d7868c",
        checkpoint_class_names=FOUR_CLASS_CHECKPOINT,
        canonical_class_names=FOUR_CLASS_CANONICAL,
        task="obb",
    ),
    YoloModelSpec(
        key="coco80_base",
        display_name="YOLO11n Base (COCO, 80 classes)",
        relative_path="pt/yolo11n.pt",
        architecture="YOLO11n Base",
        dataset_variant="COCO general-purpose (official Ultralytics pretrained)",
        expected_sha256="0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
        checkpoint_class_names=COCO80_CLASS_NAMES,
        canonical_class_names=COCO80_CLASS_NAMES,
        input_size=640,
    ),
)
_MODEL_SPECS_BY_KEY = {spec.key: spec for spec in _MODEL_SPECS}


def list_yolo_models() -> tuple[YoloModelSpec, ...]:
    return _MODEL_SPECS


def get_yolo_model(model_key: str | None = None) -> YoloModelSpec:
    key = (model_key or settings.YOLO_DEFAULT_MODEL_KEY).strip()
    spec = _MODEL_SPECS_BY_KEY.get(key)
    if spec is None:
        raise YoloModelRegistryError(f"Unknown YOLO model key: {key}")
    available, reason = spec.availability()
    if not available:
        raise YoloModelRegistryError(f"YOLO model '{key}' is unavailable: {reason}")
    return spec
