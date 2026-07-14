"""Tests for platform-local legacy checkpoint module aliases."""
from pathlib import Path
import sys

from app.integrations.legacy_checkpoint_compat import (
    install_legacy_checkpoint_modules,
    legacy_module_specs,
    legacy_source_status,
)


def test_all_registered_legacy_sources_exist() -> None:
    for model_key in (
        "four_class_asff",
        "seven_class_asff",
        "four_class_dysample",
        "seven_class_dysample",
        "four_class_evmblock",
    ):
        available, reason = legacy_source_status(model_key)
        assert available, reason
        assert legacy_module_specs(model_key)


def test_dysample_alias_uses_platform_source_without_tasks_override() -> None:
    installed = install_legacy_checkpoint_modules("four_class_dysample")
    module = sys.modules["ultralytics.nn.modules.SCAM_DySample"]

    assert installed == ("ultralytics.nn.modules.SCAM_DySample",)
    assert Path(module.__file__).name == "SCAM_DySample.py"
    assert hasattr(module, "DySample")
    assert "tasks.py" not in str(module.__file__)


def test_efficient_vim_alias_exposes_checkpoint_classes() -> None:
    installed = install_legacy_checkpoint_modules("four_class_evmblock")
    module = sys.modules["ultralytics.nn.AddModules.EfficientViMBlock"]

    assert installed == ("ultralytics.nn.AddModules.EfficientViMBlock",)
    assert hasattr(module, "EfficientViMBlock")
    assert hasattr(module, "C3k2_EfficientViMBlock")
