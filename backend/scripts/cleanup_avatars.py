#!/usr/bin/env python
"""
Delete avatar files in ``static/avatars`` that no account uses.

The backend already removes an avatar when its account switches to a new one
or is deleted, and prunes a user's unassigned uploads on their next upload.
This sweep catches the rest: files from before that (named
``YYYYmmddHHMMSS_hex8.ext``) and uploads whose uploader never came back.

Usage (from ``backend/``, so ``.env`` and ``static/`` resolve):
    python scripts/cleanup_avatars.py              # list orphans, delete nothing
    python scripts/cleanup_avatars.py --apply      # delete them
    python scripts/cleanup_avatars.py --min-age-hours 0 --apply

Files younger than ``--min-age-hours`` (default 24) are kept, because an
upload is unassigned until the client calls ``PUT /api/auth/profile``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services import avatar_service  # noqa: E402


def main(argv: list[str] | None = None, session_factory=SessionLocal) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="delete the files (default: only list them)")
    parser.add_argument("--min-age-hours", type=float, default=24.0, help="keep files younger than this")
    args = parser.parse_args(argv)

    db = session_factory()
    try:
        orphans = avatar_service.find_orphans(db, older_than_seconds=args.min_age_hours * 3600)
    finally:
        db.close()

    total_bytes = sum(path.stat().st_size for path in orphans)
    for path in orphans:
        print(path.name)
    action = "Deleting" if args.apply else "Would delete"
    print(f"{action} {len(orphans)} unused avatar file(s), {total_bytes / 1024:.1f} KiB.")

    if args.apply:
        failed = [path.name for path in orphans if not avatar_service.unlink_quietly(path)]
        if failed:
            print(f"Could not delete {len(failed)} file(s): {', '.join(failed)}", file=sys.stderr)
            return 1
    else:
        print("Dry run; pass --apply to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
