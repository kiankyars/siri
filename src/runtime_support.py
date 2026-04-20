from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def log_error(error_log: Path, message: str) -> None:
    error_log.parent.mkdir(parents=True, exist_ok=True)
    with error_log.open("a") as handle:
        handle.write(f"{message}\n")


def load_state(state_path: Path) -> dict[str, object]:
    if not state_path.exists():
        return {"schema_version": 1, "records": {}}
    return json.loads(state_path.read_text())


def save_state(state_path: Path, state: dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def file_flags(file_path: Path) -> str:
    result = subprocess.run(
        ["stat", "-f", "%Sf", str(file_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def ensure_local_file(file_path: Path, timeout: int = 120, poll_interval: float = 2.0) -> bool:
    if "dataless" not in file_flags(file_path):
        return True
    subprocess.run(["brctl", "download", str(file_path)], check=False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if "dataless" not in file_flags(file_path):
            return True
        time.sleep(poll_interval)
    return False
