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
        expected_sha256="09e93bae837d9d092d7b538034c6893fbe20f0f08c6b7c0a54ecc0138cce322b",
        checkpoint_class_names=SEVEN_CLASS_CHECKPOINT,
        canonical_class_names=SEVEN_CLASS_CANONICAL,
    ),
    YoloModelSpec(
        key="seven_class_asff",
        display_name="YOLO11n + ASFF (7 classes)",
        relative_path="pt/7classes/yolo11n_asff.pt",
        architecture="YOLO11n + ASFF",
        dataset_variant="7-class multimodal",
        expected_sha256="40479020fc96399858e4cb009cf80f181e290a4f1c56002a0754b42c1660210b",
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
        expected_sha256="7d0558155460b75865b29d5e6392e0e2307ee2d98738b7f254595d18ce8bb430",
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
        selectable=False,
        disabled_reason="OBB output is not compatible with the current axis-aligned bounding-box pipeline.",
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
