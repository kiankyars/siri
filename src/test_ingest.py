from __future__ import annotations

import plistlib
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.import_voice_memos import (
    Config,
    VoiceMemoMetadata,
    build_prompt,
    load_routes,
    process_voice_memos,
    run_codex,
    select_changed_voice_memos,
)


class VoiceMemoPromptTests(unittest.TestCase):
    def test_routes_are_accent_insensitive(self) -> None:
        self.assertEqual(load_routes(), {"monde": "monde", "reflexion": "réflexion"})

    def test_prompt_contains_only_recording_context_and_skill_invocation(self) -> None:
        prompt = build_prompt(
            "réflexion",
            Path("/tmp/example.m4a"),
            datetime(2026, 3, 29, 20, tzinfo=timezone.utc),
        )

        self.assertEqual(
            prompt,
            (
                "Use $process-voice-memo.\n\n"
                "Recording: /tmp/example.m4a\n"
                "Recorded: 2026-03-29\n"
                "Route: réflexion\n\n"
                "Process it into the vault."
            ),
        )


class VoiceMemoLaunchdTests(unittest.TestCase):
    def test_voice_memos_watcher_has_eight_minute_fallback(self) -> None:
        template_path = (
            Path(__file__).resolve().parent.parent
            / "com.siri.voice-memos.plist.template"
        )

        with template_path.open("rb") as template_file:
            launchd_config = plistlib.load(template_file)

        self.assertEqual(launchd_config["StartInterval"], 480)


class CodexInvocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            codex_bin="/opt/homebrew/bin/codex",
            ffprobe_bin="/opt/homebrew/bin/ffprobe",
            state_path=Path("/tmp/state.json"),
            error_log=Path("/tmp/error.log"),
            vault_root=Path("/Users/kian/obsidian"),
            voice_memos_dir=Path("/Users/kian/Library/Voice Memos"),
        )

    @patch("src.import_voice_memos.subprocess.run")
    def test_codex_runs_from_the_vault(self, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stderr = ""

        self.assertTrue(run_codex(self.config, "prompt"))

        command = run.call_args.args[0]
        self.assertEqual(command[command.index("-C") + 1], "/Users/kian/obsidian")
        self.assertEqual(run.call_args.kwargs["cwd"], "/Users/kian/obsidian")
        self.assertEqual(run.call_args.kwargs["input"], "prompt")

    @patch("src.import_voice_memos.log_error")
    @patch("src.import_voice_memos.run_codex", return_value=False)
    @patch("src.import_voice_memos.save_state")
    @patch("src.import_voice_memos.load_state", return_value={"records": {}})
    @patch("src.import_voice_memos.wait_for_stable_file", return_value=True)
    @patch("src.import_voice_memos.ensure_local_file", return_value=True)
    def test_codex_failure_leaves_recording_unprocessed(
        self,
        _ensure_local,
        _wait_for_stable,
        load_state,
        save_state,
        _run_codex,
        _log_error,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "memo.m4a"
            source.touch()
            resolved_source = str(source.resolve())
            metadata = VoiceMemoMetadata(
                title="monde",
                recorded_at=datetime(2026, 3, 29, 20, tzinfo=timezone.utc),
                voice_memo_uuid="memo-id",
            )

            with (
                patch(
                    "src.import_voice_memos.discover_voice_memos", return_value=[source]
                ),
                patch("src.import_voice_memos.probe_voice_memo", return_value=metadata),
                patch("src.import_voice_memos.time.sleep"),
            ):
                self.assertEqual(process_voice_memos(self.config, dry_run=False), 1)

        self.assertEqual(load_state.return_value["records"], {})
        save_state.assert_called_once()
        saved_state = save_state.call_args.args[1]
        self.assertNotIn(resolved_source, saved_state["observed_versions"])

    def test_importer_rescans_for_recordings_that_arrive_during_a_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.m4a"
            late = Path(temp_dir) / "late.m4a"
            first.write_bytes(b"first")
            metadata = {
                first: VoiceMemoMetadata(
                    title="not-routed",
                    recorded_at=datetime(2026, 8, 3, 19, tzinfo=timezone.utc),
                    voice_memo_uuid="first-id",
                ),
                late: VoiceMemoMetadata(
                    title="monde",
                    recorded_at=datetime(2026, 8, 3, 20, tzinfo=timezone.utc),
                    voice_memo_uuid="late-id",
                ),
            }
            discovery_count = 0

            def discover(_library_dir):
                nonlocal discovery_count
                discovery_count += 1
                if discovery_count == 1:
                    return [first]
                if not late.exists():
                    late.write_bytes(b"late")
                return [first, late]

            with (
                patch(
                    "src.import_voice_memos.discover_voice_memos",
                    side_effect=discover,
                ),
                patch("src.import_voice_memos.ensure_local_file", return_value=True),
                patch("src.import_voice_memos.wait_for_stable_file", return_value=True),
                patch(
                    "src.import_voice_memos.probe_voice_memo",
                    side_effect=lambda source, _ffprobe: metadata[source],
                ),
                patch(
                    "src.import_voice_memos.load_state", return_value={"records": {}}
                ),
                patch("src.import_voice_memos.save_state") as save_state,
                patch(
                    "src.import_voice_memos.run_codex", return_value=True
                ) as run_codex,
                patch("src.import_voice_memos.log_error"),
                patch("src.import_voice_memos.time.sleep"),
            ):
                self.assertEqual(process_voice_memos(self.config, dry_run=False), 1)

        run_codex.assert_called_once()
        self.assertEqual(save_state.call_count, 2)

    def test_durable_version_index_skips_unchanged_recordings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "memo.m4a"
            source.write_bytes(b"memo")
            observed_versions: dict[str, str] = {}
            self.assertEqual(
                select_changed_voice_memos([source], observed_versions), [source]
            )
            state = {
                "schema_version": 2,
                "records": {},
                "observed_versions": observed_versions,
            }

            with (
                patch(
                    "src.import_voice_memos.discover_voice_memos",
                    return_value=[source],
                ),
                patch("src.import_voice_memos.load_state", return_value=state),
                patch("src.import_voice_memos.ensure_local_file") as ensure_local,
                patch("src.import_voice_memos.probe_voice_memo") as probe,
                patch("src.import_voice_memos.save_state") as save_state,
                patch("src.import_voice_memos.time.sleep"),
            ):
                self.assertEqual(process_voice_memos(self.config, dry_run=False), 0)

        ensure_local.assert_not_called()
        probe.assert_not_called()
        save_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
