from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_PROMPT = """Transcribe all intelligible speech in this recording faithfully.
Preserve the spoken wording and natural speaker turns. Use generic speaker labels when useful.
Do not summarize, omit substantive content, or infer anyone's identity unless their name is explicitly spoken.
Mark genuinely unintelligible passages as [unclear]. Output only the transcript."""
MIME_TYPES = {
    ".aac": "audio/aac",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mp3",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".wav": "audio/wav",
}


def audio_mime_type(audio_file: Path) -> str:
    try:
        return MIME_TYPES[audio_file.suffix.lower()]
    except KeyError as err:
        supported = ", ".join(sorted(MIME_TYPES))
        raise ValueError(
            f"Unsupported audio extension {audio_file.suffix!r}; expected one of: {supported}"
        ) from err


def wait_for_active_file(
    client: genai.Client,
    uploaded_file: types.File,
    timeout: float = 120,
    poll_interval: float = 2,
) -> types.File:
    deadline = time.monotonic() + timeout
    current_file = uploaded_file
    while time.monotonic() < deadline:
        if current_file.state == types.FileState.ACTIVE:
            return current_file
        if current_file.state == types.FileState.FAILED:
            raise RuntimeError(
                f"Gemini failed to process uploaded file {current_file.name}"
            )
        time.sleep(poll_interval)
        current_file = client.files.get(name=current_file.name)
    raise TimeoutError(
        f"Gemini did not finish processing {uploaded_file.name} within {timeout:g}s"
    )


def build_prompt(context: str | None = None) -> str:
    if not context:
        return DEFAULT_PROMPT
    return (
        f"{DEFAULT_PROMPT}\n\n"
        "The following context is a spelling hint only, not evidence that a word or name was spoken:\n"
        f"{context.strip()}"
    )


def transcribe_audio(
    client: genai.Client,
    audio_file: Path,
    context: str | None = None,
) -> str:
    audio_file = audio_file.expanduser().resolve()
    if not audio_file.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    if audio_file.stat().st_size == 0:
        raise ValueError(f"Audio file is empty: {audio_file}")

    mime_type = audio_mime_type(audio_file)
    uploaded_file = client.files.upload(
        file=audio_file,
        config=types.UploadFileConfig(
            display_name=audio_file.name,
            mime_type=mime_type,
        ),
    )
    try:
        active_file = wait_for_active_file(client, uploaded_file)
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[active_file, build_prompt(context)],
        )
        transcript = (response.text or "").strip()
        if not transcript:
            raise RuntimeError(f"{DEFAULT_MODEL} returned an empty transcript")
        return transcript
    finally:
        if uploaded_file.name:
            try:
                client.files.delete(name=uploaded_file.name)
            except errors.APIError as err:
                print(
                    f"Warning: could not delete Gemini upload {uploaded_file.name}: {err}",
                    file=sys.stderr,
                )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Transcribe an audio file with {DEFAULT_MODEL}."
    )
    parser.add_argument("audio_file", type=Path)
    parser.add_argument(
        "--context",
        help="Optional spelling hints such as likely names or specialist vocabulary.",
    )
    parser.add_argument("-o", "--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY is missing from {REPO_ROOT / '.env'}")

    client = genai.Client(api_key=api_key)
    transcript = transcribe_audio(
        client,
        args.audio_file,
        context=args.context,
    )
    if args.output:
        output_path = args.output.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{transcript}\n")
    else:
        print(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
