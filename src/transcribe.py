from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from send2trash import send2trash

load_dotenv()

MODEL_FALLBACKS = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
DEFAULT_ERROR_LOG = Path(__file__).resolve().parent.parent / "logs" / "siri_errors.log"
COURSE_HEADING = "## Course"
HEADING_RE = re.compile(r"(?m)^## .*$")


@dataclass(frozen=True)
class SourceConfig:
    source_dir: Path
    section_heading: str | None


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def load_config() -> tuple[genai.Client, list[SourceConfig], Path, Path]:
    client = genai.Client(api_key=required_env("GEMINI_API_KEY"))
    daily_dir = Path(required_env("OBSIDIAN_DAILY_DIR")).expanduser()
    error_log = DEFAULT_ERROR_LOG
    sources = [
        SourceConfig(Path(required_env("VOICE_MEMOS_DIR_0")).expanduser(), None),
        SourceConfig(Path(required_env("VOICE_MEMOS_DIR_1")).expanduser(), COURSE_HEADING),
    ]
    return client, sources, daily_dir, error_log


def log_error(error_log: Path, message: str) -> None:
    error_log.parent.mkdir(parents=True, exist_ok=True)
    with error_log.open("a") as handle:
        handle.write(f"{message}\n")


def extract_recorded_datetime(file_path: Path) -> datetime:
    match = re.search(r"(\d{4}-\d{2}-\d{2}).*?(\d{2}\.\d{2}\.\d{2})", file_path.name)
    if not match:
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H.%M.%S")


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
    """Download iCloud file and block until it's materialized. Returns True if local."""
    if "dataless" not in file_flags(file_path):
        return True
    subprocess.run(["brctl", "download", str(file_path)], check=False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if "dataless" not in file_flags(file_path):
            return True
        time.sleep(poll_interval)
    return False


def format_transcript_as_bullets(
    client: genai.Client,
    audio_file: Path,
    error_log: Path,
) -> str | None:
    prompt = (
        "Convert this transcript into markdown hyphen bullets. "
        "Avoid over-splitting. Output bullets only. Do not include timestamps. Do not modify the transcript."
    )
    audio_bytes = audio_file.read_bytes()
    contents = [prompt, types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp4")]
    max_retries = 3
    fallback_errors: list[str] = []
    for model_name in MODEL_FALLBACKS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(model=model_name, contents=contents)
                return (response.text or "").strip()
            except errors.APIError as err:
                fallback_errors.append(f"{model_name} (attempt {attempt + 1}): {err}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as err:
                fallback_errors.append(f"{model_name} (attempt {attempt + 1}): {err}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details = " | ".join(fallback_errors) if fallback_errors else "no model error captured"
    message = f"[{timestamp}] Failed to process file: {audio_file}. All model fallbacks failed. Errors: {details}"
    log_error(error_log, message)


def normalize_block(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())


def join_blocks(*blocks: str) -> str:
    cleaned = [block.strip("\n") for block in blocks if block and block.strip("\n")]
    if not cleaned:
        return ""
    return "\n\n".join(cleaned) + "\n"


def insert_into_root(current_text: str, addition: str) -> str:
    heading_match = HEADING_RE.search(current_text)
    if heading_match is None:
        return join_blocks(current_text, addition)
    return join_blocks(current_text[: heading_match.start()], addition, current_text[heading_match.start() :])


def find_section_bounds(current_text: str, heading: str) -> tuple[int, int, int] | None:
    section_match = re.search(rf"(?m)^{re.escape(heading)}\s*$", current_text)
    if section_match is None:
        return None
    next_heading_match = HEADING_RE.search(current_text, section_match.end())
    section_end = next_heading_match.start() if next_heading_match else len(current_text)
    return section_match.start(), section_match.end(), section_end


def insert_into_section(current_text: str, heading: str, addition: str) -> str:
    bounds = find_section_bounds(current_text, heading)
    if bounds is None:
        heading_match = HEADING_RE.search(current_text)
        new_section = join_blocks(heading, addition)
        if heading_match is None:
            return join_blocks(current_text, new_section)
        return join_blocks(current_text[: heading_match.start()], new_section, current_text[heading_match.start() :])

    section_start, heading_end, section_end = bounds
    section_heading = current_text[section_start:heading_end]
    section_body = current_text[heading_end:section_end]
    return join_blocks(
        current_text[:section_start],
        join_blocks(section_heading, section_body, addition),
        current_text[section_end:],
    )


def build_note_text(current_text: str, addition: str, section_heading: str | None) -> str:
    normalized_addition = normalize_block(addition)
    if not normalized_addition:
        return current_text
    if section_heading is None:
        return insert_into_root(current_text, normalized_addition)
    return insert_into_section(current_text, section_heading, normalized_addition)


def write_note(target_file: Path, text: str) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(text)


def trash_file(file_path: Path) -> None:
    send2trash(str(file_path))


def process_audio(
    client: genai.Client,
    audio_file: Path,
    source: SourceConfig,
    daily_dir: Path,
    error_log: Path,
) -> None:
    if not ensure_local_file(audio_file):
        log_error(error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Timed out downloading iCloud file: {audio_file}")
        return
    recorded_at = extract_recorded_datetime(audio_file)
    date_str = recorded_at.strftime("%Y-%m-%d")
    target_file = daily_dir / f"{date_str}.md"
    bullets = format_transcript_as_bullets(client, audio_file, error_log)
    if bullets is None:
        return
    original_exists = target_file.exists()
    original_text = target_file.read_text() if original_exists else ""
    updated_text = build_note_text(original_text, bullets, source.section_heading)
    if updated_text == original_text:
        return
    try:
        write_note(target_file, updated_text)
        trash_file(audio_file)
    except Exception as err:
        try:
            if original_exists:
                write_note(target_file, original_text)
            elif target_file.exists():
                target_file.unlink()
        except Exception as rollback_err:
            log_error(
                error_log,
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Failed to rollback note after processing error for {audio_file}: {rollback_err}",
            )
        log_error(error_log, f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Failed to process file {audio_file}: {err}")


def main() -> None:
    client, sources, daily_dir, error_log = load_config()
    for source in sources:
        source_dir = source.source_dir
        if not source_dir.exists():
            continue
        for audio_file in sorted(source_dir.iterdir()):
            if not audio_file.is_file() or audio_file.name.startswith("."):
                continue
            if audio_file.suffix.lower() != ".m4a":
                continue
            process_audio(client, audio_file, source, daily_dir, error_log)


if __name__ == "__main__":
    main()
