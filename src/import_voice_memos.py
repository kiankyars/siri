from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

try:
    from .runtime_support import ensure_local_file, load_state, log_error, required_env, save_state
except ImportError:
    from runtime_support import ensure_local_file, load_state, log_error, required_env, save_state

load_dotenv()

DEFAULT_ERROR_LOG = Path(__file__).resolve().parent.parent / "logs" / "siri_errors.log"
DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "logs" / "voice_memos_import_state.json"
DEFAULT_LIBRARY_DIR = Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings"
DEFAULT_ENDPOINTS_PATH = Path(__file__).resolve().with_name("obsidian_audio_routing_endpoints.json")
DEFAULT_PROMPT_RENDERER = Path(__file__).resolve().with_name("render_codex_audio_prompt.py")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class Config:
    codex_bin: str
    ffprobe_bin: str
    endpoints_path: Path
    prompt_renderer: Path
    state_path: Path
    error_log: Path
    repo_root: Path
    vault_root: Path
    voice_memos_dir: Path


@dataclass(frozen=True)
class VoiceMemoMetadata:
    title: str
    recorded_at: datetime
    voice_memo_uuid: str | None


def resolve_binary(name: str, *candidates: str) -> str:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    resolved = shutil.which(name)
    if resolved:
        return resolved
    candidate_list = ", ".join(candidates) if candidates else name
    raise RuntimeError(f"Could not find executable `{name}`. Checked: {candidate_list}")


def load_config() -> Config:
    repo_root = Path(__file__).resolve().parent.parent
    daily_dir = Path(required_env("OBSIDIAN_DAILY_DIR")).expanduser().resolve()
    return Config(
        codex_bin=resolve_binary("codex", "/opt/homebrew/bin/codex", "/usr/local/bin/codex"),
        ffprobe_bin=resolve_binary("ffprobe", "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"),
        endpoints_path=Path(os.getenv("VOICE_MEMOS_ENDPOINTS_PATH", str(DEFAULT_ENDPOINTS_PATH))).expanduser(),
        prompt_renderer=Path(os.getenv("VOICE_MEMOS_PROMPT_RENDERER", str(DEFAULT_PROMPT_RENDERER))).expanduser(),
        state_path=Path(os.getenv("VOICE_MEMOS_STATE_PATH", str(DEFAULT_STATE_PATH))).expanduser(),
        error_log=Path(os.getenv("VOICE_MEMOS_ERROR_LOG", str(DEFAULT_ERROR_LOG))).expanduser(),
        repo_root=repo_root,
        vault_root=daily_dir.parent,
        voice_memos_dir=DEFAULT_LIBRARY_DIR,
    )


def normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return NON_ALNUM_RE.sub("-", ascii_only.lower()).strip("-")


def load_endpoint_configs(endpoints_path: Path) -> dict[str, str]:
    payload = json.loads(endpoints_path.read_text())
    return {normalize_token(endpoint): endpoint for endpoint in payload}


def discover_voice_memos(library_dir: Path) -> list[Path]:
    if not library_dir.exists():
        raise RuntimeError(f"Voice Memos directory not found: {library_dir}")
    return sorted(
        (path for path in library_dir.glob("*.m4a") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def wait_for_stable_file(file_path: Path, timeout: int = 60, poll_interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    last_size: int | None = None
    stable_polls = 0
    while time.monotonic() < deadline:
        if not file_path.exists():
            return False
        current_size = file_path.stat().st_size
        if current_size > 0 and current_size == last_size:
            stable_polls += 1
            if stable_polls >= 2:
                return True
        else:
            stable_polls = 0
        last_size = current_size
        time.sleep(poll_interval)
    return False


def probe_voice_memo(file_path: Path, ffprobe_bin: str) -> VoiceMemoMetadata:
    result = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format_tags=title,creation_time,voice-memo-uuid",
            "-of",
            "json",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffprobe failed for {file_path}")

    payload = json.loads(result.stdout or "{}")
    tags = payload.get("format", {}).get("tags", {})
    title = (tags.get("title") or "").strip()
    created_at_raw = (tags.get("creation_time") or "").strip()
    if created_at_raw:
        recorded_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    else:
        recorded_at = datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()
    return VoiceMemoMetadata(
        title=title,
        recorded_at=recorded_at,
        voice_memo_uuid=(tags.get("voice-memo-uuid") or "").strip() or None,
    )


def is_processed(records: dict[str, object], uuid: str) -> bool:
    record = records.get(uuid)
    return isinstance(record, dict) and bool(record.get("processed_at"))


def state_keys_for_memo(file_path: Path, metadata: VoiceMemoMetadata) -> list[str]:
    resolved_path = str(file_path.resolve())
    if metadata.voice_memo_uuid:
        return [metadata.voice_memo_uuid, resolved_path]
    return [resolved_path]


def build_prompt(config: Config, endpoint: str, audio_file: Path, recorded_at: datetime) -> str:
    result = subprocess.run(
        [
            sys.executable,
            str(config.prompt_renderer),
            "--endpoint",
            endpoint,
            "--audio",
            str(audio_file),
            "--date",
            recorded_at.astimezone().strftime("%Y-%m-%d"),
            "--vault-root",
            str(config.vault_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to build Codex prompt.")
    prompt = result.stdout.strip()
    if not prompt:
        raise RuntimeError("Prompt renderer returned empty output.")
    return prompt


def run_codex(config: Config, prompt: str) -> None:
    result = subprocess.run(
        [
            config.codex_bin,
            "exec",
            "--full-auto",
            "-C",
            str(config.repo_root),
            "--add-dir",
            str(config.vault_root),
            "--add-dir",
            str(config.voice_memos_dir),
            "-",
        ],
        input=prompt,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"codex exec failed with exit code {result.returncode}")


def process_voice_memos(config: Config, dry_run: bool) -> int:
    endpoint_configs = load_endpoint_configs(config.endpoints_path)
    state = load_state(config.state_path)
    records = state.setdefault("records", {})
    matches = 0
    source_paths = discover_voice_memos(config.voice_memos_dir)
    first_path = source_paths[0].name if source_paths else "none"
    log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Trace importer start: count={len(source_paths)} first={first_path}")

    for source_path in source_paths:
        if not source_path.exists():
            continue
        if not ensure_local_file(source_path):
            log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Timed out downloading Voice Memo: {source_path}")
            continue
        if not wait_for_stable_file(source_path):
            log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Voice Memo did not stabilize: {source_path}")
            continue

        try:
            metadata = probe_voice_memo(source_path, config.ffprobe_bin)
        except Exception as err:
            log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Failed to inspect Voice Memo {source_path}: {err}")
            continue

        endpoint = endpoint_configs.get(normalize_token(metadata.title))
        if endpoint is None:
            continue
        state_keys = state_keys_for_memo(source_path, metadata)
        if any(is_processed(records, key) for key in state_keys):
            continue
        log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Trace Voice Memo match: {source_path} -> {endpoint}")

        matches += 1
        if dry_run:
            print(f"{endpoint}: {source_path}")
            continue

        try:
            prompt = build_prompt(config, endpoint, source_path, metadata.recorded_at)
            log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Trace Codex start: {source_path}")
            run_codex(config, prompt)
            log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Trace Codex finish: {source_path}")
        except Exception as err:
            log_error(config.error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Failed to process Voice Memo {source_path}: {err}")
            continue

        record_key = metadata.voice_memo_uuid or str(source_path.resolve())
        records.pop(str(source_path.resolve()), None)
        records[record_key] = {
            "endpoint": endpoint,
            "processed_at": datetime.now().isoformat(),
            "recorded_at": metadata.recorded_at.isoformat(),
            "source_path": str(source_path.resolve()),
            "title": metadata.title,
        }
        save_state(config.state_path, state)

    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process routed Voice Memos directly from the library.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect Voice Memos and print matches without running Codex.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    matches = process_voice_memos(config, dry_run=args.dry_run)
    if args.dry_run:
        print(f"matched={matches}")


if __name__ == "__main__":
    main()
