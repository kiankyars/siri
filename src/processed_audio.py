from __future__ import annotations

import argparse
import shutil
import stat
import time
from datetime import datetime
from pathlib import Path

try:
    from .runtime_support import exclusive_file_lock
except ImportError:
    from runtime_support import exclusive_file_lock

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "processed"
RETENTION_DAYS = 7


def archive_file(file_path: Path) -> Path:
    if file_path.suffix.lower() != ".m4a" or not stat.S_ISREG(
        file_path.lstat().st_mode
    ):
        raise ValueError(f"Not a regular M4A recording: {file_path}")
    if PROCESSED_DIR.is_symlink():
        raise RuntimeError(f"Refusing symlinked archive: {PROCESSED_DIR}")
    with exclusive_file_lock(PROCESSED_DIR / ".archive.lock"):
        destination = PROCESSED_DIR / file_path.name
        suffix = 1
        while destination.exists() or destination.is_symlink():
            destination = PROCESSED_DIR / (
                f"{file_path.stem} ({suffix}){file_path.suffix}"
            )
            suffix += 1
        # Cleanup uses the same lock, including during cross-filesystem copies.
        shutil.move(str(file_path), str(destination))
        return destination


def cleanup_processed_files(
    *, dry_run: bool = False, now: float | None = None
) -> list[Path]:
    if PROCESSED_DIR.is_symlink():
        raise RuntimeError(f"Refusing symlinked archive: {PROCESSED_DIR}")
    if not PROCESSED_DIR.exists():
        return []
    cutoff = (time.time() if now is None else now) - RETENTION_DAYS * 86400
    expired: list[Path] = []
    with exclusive_file_lock(PROCESSED_DIR / ".archive.lock"):
        for file_path in sorted(PROCESSED_DIR.iterdir()):
            if file_path.name.startswith(".") or file_path.suffix.lower() != ".m4a":
                continue
            info = file_path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_mtime >= cutoff:
                continue
            if not dry_run:
                file_path.unlink()
            expired.append(file_path)
    return expired


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Permanently delete processed M4A files older than {RETENTION_DAYS} days."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    expired = cleanup_processed_files(dry_run=args.dry_run)
    action = "Would delete" if args.dry_run else "Deleted"
    for file_path in expired:
        print(f"{action}: {file_path}")
    print(
        f"[{datetime.now().astimezone():%Y-%m-%d %H:%M:%S %Z}] {action} {len(expired)} expired recordings."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
