"""Compatibility aliases for checkpoints trained with legacy custom modules.

PyTorch checkpoints record the fully-qualified Python module path for custom
classes.  The platform keeps the original source files in the repository and
registers only the exact historical paths required by approved checkpoints.
It deliberately does not replace the installed Ultralytics ``tasks.py``.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from dataclasses import dataclass
from functools import lru_cache
from hashlib import file_digest
from pathlib import Path
from threading import Lock

_PLATFORM_ROOT = Path(__file__).resolve().parents[3]
_INSTALL_LOCK = Lock()


class LegacyCheckpointCompatibilityError(RuntimeError):
    """Raised when an approved legacy checkpoint module cannot be installed."""


@dataclass(frozen=True)
class LegacyModuleSpec:
    module_name: str
    source_path: Path


_ASFF = LegacyModuleSpec(
    module_name="ultralytics.nn.modules.ASFFHead",
    source_path=_PLATFORM_ROOT / "models/custom_modules/ASFFHead.py",
)
_DYSAMPLE = LegacyModuleSpec(
    module_name="ultralytics.nn.modules.SCAM_DySample",
    source_path=_PLATFORM_ROOT / "SCAM_DySample.py",
)
_EFFICIENT_VIM = LegacyModuleSpec(
    module_name="ultralytics.nn.AddModules.EfficientViMBlock",
    source_path=_PLATFORM_ROOT / "AddModules/EfficientViMBlock.py",
)

_MODEL_MODULES: dict[str, tuple[LegacyModuleSpec, ...]] = {
    "four_class_asff": (_ASFF,),
    "seven_class_asff": (_ASFF,),
    "four_class_dysample": (_DYSAMPLE,),
    "seven_class_dysample": (_DYSAMPLE,),
    "four_class_evmblock": (_EFFICIENT_VIM,),
}


def legacy_module_specs(model_key: str) -> tuple[LegacyModuleSpec, ...]:
    """Return the hard-coded compatibility modules for an approved model key."""
    return _MODEL_MODULES.get(model_key, ())


def legacy_source_status(model_key: str) -> tuple[bool, str | None]:
    """Check that every compatibility source required by a model is present."""
    missing = [
        str(spec.source_path.relative_to(_PLATFORM_ROOT))
        for spec in legacy_module_specs(model_key)
        if not spec.source_path.is_file()
    ]
    if missing:
        return False, f"Required compatibility source is missing: {', '.join(missing)}"
    return True, None


def legacy_source_fingerprints(model_key: str) -> dict[str, str]:
    """Return SHA-256 fingerprints for runtime module sources used by a model."""
    fingerprints: dict[str, str] = {}
    for spec in legacy_module_specs(model_key):
        if spec.source_path.is_file():
            stat = spec.source_path.stat()
            fingerprints[spec.module_name] = _source_sha256(
                str(spec.source_path),
                stat.st_size,
                stat.st_mtime_ns,
            )
    return fingerprints


@lru_cache(maxsize=16)
def _source_sha256(path: str, _size: int, _mtime_ns: int) -> str:
    with Path(path).open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def install_legacy_checkpoint_modules(model_key: str) -> tuple[str, ...]:
    """Register exact legacy module paths before Ultralytics loads a checkpoint."""
    specs = legacy_module_specs(model_key)
    if not specs:
        return ()

    available, reason = legacy_source_status(model_key)
    if not available:
        raise LegacyCheckpointCompatibilityError(reason)

    installed: list[str] = []
    with _INSTALL_LOCK:
        for spec in specs:
            _install_module(spec)
            installed.append(spec.module_name)
    return tuple(installed)


def _install_module(spec: LegacyModuleSpec) -> None:
    source_path = spec.source_path.resolve()
    try:
        source_path.relative_to(_PLATFORM_ROOT)
    except ValueError as exc:  # pragma: no cover - hard-coded defensive check
        raise LegacyCheckpointCompatibilityError(
            f"Compatibility source is outside the platform root: {source_path}"
        ) from exc

    existing = sys.modules.get(spec.module_name)
    existing_file = getattr(existing, "__file__", None)
    if existing_file and Path(existing_file).resolve() == source_path:
        return

    parent_name, attribute = spec.module_name.rsplit(".", 1)
    parent = _ensure_parent_package(parent_name, source_path.parent)
    module_spec = importlib.util.spec_from_file_location(spec.module_name, source_path)
    if module_spec is None or module_spec.loader is None:
        raise LegacyCheckpointCompatibilityError(
            f"Unable to create import spec for {spec.module_name}"
        )

    module = importlib.util.module_from_spec(module_spec)
    previous = sys.modules.get(spec.module_name)
    sys.modules[spec.module_name] = module
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:
        if previous is None:
            sys.modules.pop(spec.module_name, None)
        else:
            sys.modules[spec.module_name] = previous
        raise LegacyCheckpointCompatibilityError(
            f"Unable to load compatibility module {spec.module_name}: {exc}"
        ) from exc
    setattr(parent, attribute, module)


def _ensure_parent_package(parent_name: str, source_dir: Path):
    try:
        return importlib.import_module(parent_name)
    except ModuleNotFoundError:
        grandparent_name, attribute = parent_name.rsplit(".", 1)
        grandparent = importlib.import_module(grandparent_name)
        package = types.ModuleType(parent_name)
        package.__package__ = parent_name
        package.__path__ = [str(source_dir)]
        sys.modules[parent_name] = package
        setattr(grandparent, attribute, package)
        return package
