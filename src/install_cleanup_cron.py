from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
BEGIN = "# BEGIN siri processed audio cleanup"
END = "# END siri processed audio cleanup"


def update_crontab(current: str, command: str | None) -> str:
    lines = current.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if starts or ends:
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            raise RuntimeError("Malformed Siri cleanup block in crontab")
        del lines[starts[0] : ends[0] + 1]
    result = "".join(lines)
    if command is not None:
        if result and not result.endswith("\n"):
            result += "\n"
        result += f"{BEGIN}\n0 10 * * * {command}\n{END}\n"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the daily Siri cleanup cron job."
    )
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    result = subprocess.run(
        ["/usr/bin/crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode and "no crontab for" not in result.stderr:
        raise RuntimeError(result.stderr.strip() or "Cannot read crontab")
    current = result.stdout if result.returncode == 0 else ""
    command = None
    if not args.remove:
        python = REPO_DIR / ".venv/bin/python"
        if not python.is_file():
            raise RuntimeError("Run uv sync before installing cleanup.")
        log = REPO_DIR / "logs/cleanup_processed.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        command = (
            shlex.join([str(python), str(REPO_DIR / "src/processed_audio.py")])
            + f" >> {shlex.quote(str(log))} 2>&1"
        ).replace("%", r"\%")
    updated = update_crontab(current, command)
    if updated != current:
        subprocess.run(["/usr/bin/crontab", "-"], input=updated, text=True, check=True)
    print(
        "Removed Siri cleanup cron job."
        if args.remove
        else "Installed Siri cleanup: daily at 10:00 local time."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
