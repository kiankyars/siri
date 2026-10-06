from __future__ import annotations

import os
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.install_cleanup_cron import update_crontab
from src.processed_audio import RETENTION_DAYS, archive_file, cleanup_processed_files
from src.simple_endpoints import SimpleEndpoint
from src.transcribe import process_audio


class ProcessedAudioTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.processed = self.root / "processed"
        patcher = patch("src.processed_audio.PROCESSED_DIR", self.processed)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_archive_preserves_recordings_with_colliding_names_and_dates(self) -> None:
        source = self.root / "recording.m4a"
        source.write_bytes(b"first recording")
        os.utime(source, (1000, 1000))
        first = archive_file(source)
        self.assertFalse(source.exists())
        source.write_bytes(b"second recording")
        os.utime(source, (2000, 2000))
        second = archive_file(source)

        self.assertEqual(first.read_bytes(), b"first recording")
        self.assertEqual(second.read_bytes(), b"second recording")
        self.assertNotEqual(first, second)
        self.assertEqual(first.stat().st_mtime, 1000)
        self.assertEqual(second.stat().st_mtime, 2000)
        self.assertFalse(source.exists())

    def test_failed_archive_retains_source(self) -> None:
        source = self.root / "recording.m4a"
        source.write_bytes(b"keep me")
        with (
            patch("src.processed_audio.shutil.move", side_effect=OSError("disk full")),
            self.assertRaises(OSError),
        ):
            archive_file(source)
        self.assertEqual(source.read_bytes(), b"keep me")

    def test_cleanup_respects_exact_cutoff_and_only_deletes_top_level_audio(
        self,
    ) -> None:
        self.processed.mkdir()
        now = 10_000_000
        cutoff = now - RETENTION_DAYS * 86400
        for name, modified in (
            ("old.m4a", cutoff - 1),
            ("boundary.m4a", cutoff),
            ("recent.m4a", cutoff + 1),
            ("keep.txt", cutoff - 1),
            (".hidden.m4a", cutoff - 1),
        ):
            path = self.processed / name
            path.write_bytes(b"recording")
            os.utime(path, (modified, modified))
        outside = self.root / "outside.m4a"
        outside.write_bytes(b"outside")
        os.utime(outside, (cutoff - 1, cutoff - 1))
        (self.processed / "linked.m4a").symlink_to(outside)
        nested = self.processed / "nested.m4a"
        nested.mkdir()
        (nested / "keep.m4a").write_bytes(b"nested")

        expected = [self.processed / "old.m4a"]
        self.assertEqual(cleanup_processed_files(now=now, dry_run=True), expected)
        self.assertTrue(expected[0].exists())
        self.assertEqual(cleanup_processed_files(now=now), expected)
        self.assertFalse(expected[0].exists())
        self.assertEqual(
            {p.name for p in self.processed.iterdir()},
            {
                ".archive.lock",
                "boundary.m4a",
                "recent.m4a",
                "keep.txt",
                ".hidden.m4a",
                "linked.m4a",
                "nested.m4a",
            },
        )
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_cleanup_rejects_symlinked_archive(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        self.processed.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            cleanup_processed_files()

    def test_ingestion_archives_only_after_a_successful_note_write(self) -> None:
        source = self.root / "2026-10-06 08.00.00.m4a"
        source.write_bytes(b"recording")
        daily = self.root / "daily"
        endpoint = SimpleEndpoint("course", "## Course à Pied", self.root)
        with (
            patch("src.transcribe.ensure_local_file", return_value=True),
            patch(
                "src.transcribe.format_transcript_as_bullets", return_value="- Capture"
            ),
            patch("src.transcribe.vault_operation_lock", side_effect=nullcontext),
        ):
            with patch(
                "src.transcribe.write_capture_to_note", side_effect=OSError("busy")
            ):
                self.assertFalse(
                    process_audio(
                        Mock(), source, endpoint, daily, self.root / "errors.log"
                    )
                )
            self.assertTrue(source.exists())
            self.assertFalse(self.processed.exists())
            self.assertTrue(
                process_audio(Mock(), source, endpoint, daily, self.root / "errors.log")
            )

        self.assertFalse(source.exists())
        self.assertEqual((self.processed / source.name).read_bytes(), b"recording")
        self.assertEqual(
            (daily / "2026-10-06.md").read_text(), "## Course à Pied\n\n- Capture\n"
        )


class CleanupCronTests(unittest.TestCase):
    def test_install_is_idempotent_and_removal_preserves_other_jobs(self) -> None:
        original = 'MAILTO=""\n15 2 * * * /usr/bin/true\n'
        command = "/path/to/python /path/to/processed_audio.py"
        installed = update_crontab(original, command)
        self.assertIn(f"0 10 * * * {command}\n", installed)
        self.assertEqual(update_crontab(installed, command), installed)
        self.assertEqual(update_crontab(installed, None), original)

    def test_malformed_managed_block_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            update_crontab("# BEGIN siri processed audio cleanup\n", "command")


if __name__ == "__main__":
    unittest.main()
