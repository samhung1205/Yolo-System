#!/usr/bin/env python
"""
Recompute and update the SHA-256 fingerprint(s) pinned in
``app/integrations/model_registry.py`` for one or more approved YOLO
checkpoints.

Why this exists
----------------
Every checkpoint in the registry is pinned to an ``expected_sha256`` value as
a tamper-detection guard (see ``YoloModelSpec.availability()``). Whenever you
drop in a newly-trained ``.pt`` file with the same filename (e.g. re-training
"YOLO11n Base (7 classes)" and replacing ``pt/7classes/yolo11n_base.pt``),
the old fingerprint no longer matches and the model becomes unselectable in
the UI ("Checkpoint fingerprint changed; registry review is required.").

This script recomputes the real hash, sanity-checks that the new checkpoint
still loads with the expected inference task + class-name mapping (so you
never accidentally "unlock" a checkpoint with a different architecture/class
set under the same key), and then edits ``model_registry.py`` in place to
update the pinned hash. It refuses to touch the file if validation fails.

Usage (run from the ``backend/`` directory, ideally inside the
``yolo-backend`` conda env so ``ultralytics`` is importable)
--------------------------------------------------------------------
    # See every registered model, its key, and whether it currently matches
    python scripts/update_model_hash.py --list

    # Update one model after dropping in a new checkpoint file
    python scripts/update_model_hash.py seven_class_base

    # Update more than one at once
    python scripts/update_model_hash.py seven_class_base seven_class_asff

    # Scan every registered model and update whichever ones changed on disk
    python scripts/update_model_hash.py --all

    # Preview what would happen without writing anything
    python scripts/update_model_hash.py --all --dry-run

After it updates the registry, restart/reload the backend (or let
``uvicorn --reload`` pick up the change) and re-check the model dropdown in
the web UI, or run: python scripts/update_model_hash.py --list
"""
from __future__ import annotations

import argparse
import re
import sys
from hashlib import file_digest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.integrations import model_registry  # noqa: E402
from app.integrations.legacy_checkpoint_compat import (  # noqa: E402
    LegacyCheckpointCompatibilityError,
    install_legacy_checkpoint_modules,
)

REGISTRY_FILE = Path(model_registry.__file__)


def _actual_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest()


def _validate_checkpoint(spec) -> tuple[bool, str]:
    """Load the checkpoint through the real loading path and check task +
    class names against what the registry expects for this key.

    Returns ``(ok, message)``.
    """
    try:
        install_legacy_checkpoint_modules(spec.key)
    except LegacyCheckpointCompatibilityError as exc:
        return False, f"legacy compatibility module unavailable: {exc}"

    try:
        from ultralytics import YOLO
    except ImportError:
        return False, "ultralytics is not installed in this environment"

    try:
        model = YOLO(str(spec.checkpoint_path))
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"failed to load checkpoint: {exc}"

    if model.task != spec.task:
        return False, (
            f"task mismatch: checkpoint is '{model.task}', registry expects '{spec.task}'"
        )

    loaded_names = {int(k): str(v) for k, v in model.names.items()}
    if loaded_names != spec.checkpoint_class_names:
        return False, (
            "class mapping mismatch: checkpoint has "
            f"{loaded_names!r}, registry expects {spec.checkpoint_class_names!r}"
        )

    return True, "task and class mapping match the registry"


def _update_registry_source(key: str, new_hash: str, *, registry_file: Path = REGISTRY_FILE) -> None:
    source = registry_file.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(key="' + re.escape(key) + r'",.*?expected_sha256=")[0-9a-f]{64}(")',
        re.DOTALL,
    )
    matches = list(pattern.finditer(source))
    if not matches:
        raise RuntimeError(
            f"could not find an expected_sha256 field for key={key!r} in {registry_file}"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"found {len(matches)} matches for key={key!r}; refusing to guess which to update"
        )

    updated = pattern.sub(rf"\g<1>{new_hash}\g<2>", source, count=1)
    registry_file.write_text(updated, encoding="utf-8")


def process_model(spec, *, dry_run: bool) -> str:
    """Returns a short status: 'unchanged' | 'updated' | 'skipped' | 'missing'."""
    path = spec.checkpoint_path
    if not path.is_file():
        print(f"[{spec.key}] SKIP — checkpoint file not found: {path}")
        return "missing"

    actual = _actual_sha256(path)
    if actual == spec.expected_sha256:
        print(f"[{spec.key}] OK — fingerprint already matches, nothing to do")
        return "unchanged"

    print(f"[{spec.key}] fingerprint mismatch detected:")
    print(f"    registry : {spec.expected_sha256}")
    print(f"    actual   : {actual}")

    ok, message = _validate_checkpoint(spec)
    if not ok:
        print(f"[{spec.key}] REFUSING to update — checkpoint failed validation: {message}")
        print(f"[{spec.key}]   -> the new file may be a different architecture/class set;")
        print(f"[{spec.key}]      double-check before manually editing the registry.")
        return "skipped"

    print(f"[{spec.key}] validation passed — {message}")
    if dry_run:
        print(f"[{spec.key}] DRY RUN — would update expected_sha256 to {actual}")
        return "updated"

    _update_registry_source(spec.key, actual)
    print(f"[{spec.key}] UPDATED expected_sha256 in {REGISTRY_FILE.relative_to(BACKEND_ROOT)}")
    return "updated"


def list_models() -> None:
    print(f"{'key':22s} {'display_name':38s} status")
    print("-" * 90)
    for spec in model_registry.list_yolo_models():
        path = spec.checkpoint_path
        if not path.is_file():
            status = "missing file"
        else:
            actual = _actual_sha256(path)
            status = "matches registry" if actual == spec.expected_sha256 else "FINGERPRINT MISMATCH"
        print(f"{spec.key:22s} {spec.display_name:38s} {status}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "keys",
        nargs="*",
        help="One or more registered model keys to update (see --list for valid keys).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check every registered model and update any whose on-disk file no longer matches the registry.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List every registered model key + display name + current fingerprint status, then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report what would change, but do not write to model_registry.py.",
    )
    args = parser.parse_args()

    if args.list:
        list_models()
        return 0

    all_specs = {spec.key: spec for spec in model_registry.list_yolo_models()}

    if args.all:
        targets = list(all_specs.values())
    elif args.keys:
        targets = []
        for key in args.keys:
            spec = all_specs.get(key)
            if spec is None:
                print(f"Unknown model key: {key!r}. Run with --list to see valid keys.", file=sys.stderr)
                return 2
            targets.append(spec)
    else:
        parser.print_help()
        return 2

    results = {"unchanged": 0, "updated": 0, "skipped": 0, "missing": 0}
    for spec in targets:
        status = process_model(spec, dry_run=args.dry_run)
        results[status] += 1
        print()

    summary = ", ".join(f"{count} {label}" for label, count in results.items() if count)
    print(f"Summary: {summary or 'nothing to do'}")

    if results["skipped"]:
        print("\nSome checkpoints failed validation and were NOT updated — review the messages above.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
