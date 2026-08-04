from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.genai import types

from src.transcribe import MODEL_NAME, format_transcript_as_bullets
from src.transcribe_audio import (
    DEFAULT_MODEL,
    audio_mime_type,
    build_prompt,
    transcribe_audio,
    wait_for_active_file,
)


class GeminiAudioTranscriptionTests(unittest.TestCase):
    def test_m4a_uses_supported_audio_mime_type(self) -> None:
        self.assertEqual(audio_mime_type(Path("recording.m4a")), "audio/mp4")

    def test_context_is_only_a_spelling_hint(self) -> None:
        prompt = build_prompt("Likely spelling: Austin")

        self.assertIn("spelling hint only", prompt)
        self.assertIn("Austin", prompt)

    def test_waits_for_uploaded_file_to_become_active(self) -> None:
        processing = SimpleNamespace(
            name="files/example",
            state=types.FileState.PROCESSING,
        )
        active = SimpleNamespace(
            name="files/example",
            state=types.FileState.ACTIVE,
        )
        client = Mock()
        client.files.get.return_value = active

        with patch("src.transcribe_audio.time.sleep"):
            result = wait_for_active_file(client, processing)

        self.assertIs(result, active)
        client.files.get.assert_called_once_with(name="files/example")

    def test_uploads_transcribes_and_deletes_audio(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "memo.m4a"
            audio_file.write_bytes(b"audio")
            uploaded = SimpleNamespace(
                name="files/example",
                uri="https://example.test/files/example",
                mime_type="audio/mp4",
                state=types.FileState.ACTIVE,
            )
            client = Mock()
            client.files.upload.return_value = uploaded
            client.models.generate_content.return_value = SimpleNamespace(
                text="Speaker 1: Hello"
            )

            transcript = transcribe_audio(client, audio_file)

        self.assertEqual(transcript, "Speaker 1: Hello")
        upload_config = client.files.upload.call_args.kwargs["config"]
        self.assertEqual(upload_config.mime_type, "audio/mp4")
        call = client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], DEFAULT_MODEL)
        self.assertIs(call.kwargs["contents"][0], uploaded)
        client.files.delete.assert_called_once_with(name="files/example")


class SimpleInboxTranscriptionTests(unittest.TestCase):
    def test_simple_inbox_is_pinned_to_gemini_36_flash(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "memo.m4a"
            audio_file.write_bytes(b"audio")
            client = Mock()
            client.models.generate_content.return_value = SimpleNamespace(
                text="- Hello"
            )

            transcript = format_transcript_as_bullets(
                client,
                audio_file,
                Path(temp_dir) / "errors.log",
            )

        self.assertEqual(transcript, "- Hello")
        self.assertEqual(
            client.models.generate_content.call_args.kwargs["model"],
            MODEL_NAME,
        )


if __name__ == "__main__":
    unittest.main()
