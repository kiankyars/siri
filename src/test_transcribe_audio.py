from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.genai import errors, types

from src.transcribe import format_transcript_as_bullets
from src.transcribe_audio import (
    audio_mime_type,
    build_prompt,
    transcribe_audio,
    transcribe_with_retries,
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

            with patch(
                "src.transcribe_audio.configured_env",
                return_value="gemini-test-model",
            ):
                transcript = transcribe_audio(client, audio_file)

        self.assertEqual(transcript, "Speaker 1: Hello")
        upload_config = client.files.upload.call_args.kwargs["config"]
        self.assertEqual(upload_config.mime_type, "audio/mp4")
        call = client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-test-model")
        self.assertIs(call.kwargs["contents"][0], uploaded)
        client.files.delete.assert_called_once_with(name="files/example")

    def test_transcription_retries_only_the_pinned_helper_path(self) -> None:
        client = Mock()
        unavailable = errors.ServerError(
            503,
            {"error": {"code": 503, "message": "unavailable", "status": "UNAVAILABLE"}},
        )
        with (
            patch(
                "src.transcribe_audio.transcribe_once",
                side_effect=[unavailable, unavailable, "Speaker 1: Hello"],
            ) as transcribe_once,
            patch(
                "src.transcribe_audio.configured_env",
                return_value="gemini-test-model",
            ),
            patch("src.transcribe_audio.time.sleep"),
        ):
            transcript = transcribe_with_retries(
                client, Path("recording.m4a"), context=None
            )

        self.assertEqual(transcript, "Speaker 1: Hello")
        self.assertEqual(transcribe_once.call_count, 3)
        self.assertTrue(
            all(
                call.kwargs["model_name"] == "gemini-test-model"
                for call in transcribe_once.call_args_list
            )
        )

    def test_invalid_m4a_uses_lossless_compatibility_remux(self) -> None:
        invalid = errors.ClientError(
            400,
            {
                "error": {
                    "code": 400,
                    "message": "Request contains an invalid argument.",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )
        with TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "memo.m4a"
            audio_file.write_bytes(b"original")
            with (
                patch(
                    "src.transcribe_audio.transcribe_with_retries",
                    side_effect=[invalid, "Speaker 1: Hello"],
                ) as transcribe_with_retries_mock,
                patch("src.transcribe_audio.remux_m4a") as remux,
                patch(
                    "src.transcribe_audio.configured_env",
                    return_value="gemini-test-model",
                ),
            ):
                transcript = transcribe_audio(Mock(), audio_file)
            self.assertEqual(audio_file.read_bytes(), b"original")

        self.assertEqual(transcript, "Speaker 1: Hello")
        remux.assert_called_once()
        remuxed_path = transcribe_with_retries_mock.call_args_list[1].args[1]
        self.assertEqual(remuxed_path.suffix, ".m4a")
        self.assertNotEqual(remuxed_path, audio_file)


class SimpleInboxTranscriptionTests(unittest.TestCase):
    def test_simple_inbox_uses_configured_gemini_model(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "memo.m4a"
            audio_file.write_bytes(b"audio")
            client = Mock()
            client.models.generate_content.return_value = SimpleNamespace(
                text="- Hello"
            )

            with patch(
                "src.transcribe.configured_env",
                return_value="gemini-test-model",
            ):
                transcript = format_transcript_as_bullets(
                    client,
                    audio_file,
                    Path(temp_dir) / "errors.log",
                )

        self.assertEqual(transcript, "- Hello")
        self.assertEqual(
            client.models.generate_content.call_args.kwargs["model"],
            "gemini-test-model",
        )

    def test_simple_inbox_retries_only_the_pinned_model(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "memo.m4a"
            audio_file.write_bytes(b"audio")
            client = Mock()
            client.models.generate_content.side_effect = RuntimeError("unavailable")

            with (
                patch(
                    "src.transcribe.configured_env",
                    return_value="gemini-test-model",
                ),
                patch("src.transcribe.time.sleep"),
                patch("src.transcribe.log_error"),
            ):
                transcript = format_transcript_as_bullets(
                    client,
                    audio_file,
                    Path(temp_dir) / "errors.log",
                )

        self.assertIsNone(transcript)
        self.assertEqual(client.models.generate_content.call_count, 3)
        self.assertTrue(
            all(
                call.kwargs["model"] == "gemini-test-model"
                for call in client.models.generate_content.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
