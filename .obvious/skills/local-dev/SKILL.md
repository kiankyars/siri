---
name: local-dev
description: Durable record of the LOCAL-DEV onboarding for kiankyars/siri — setup, sandbox layout, verification, gotchas.
---

# local-dev — siri

Onboarding run: 2026-09-24. Stack is a single Python CLI; "local dev" means a
synced `.venv`, valid `.env`, and the mocked-test/lint gates plus a flow run.

## Setup steps that worked

1. Install uv if missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   (lands in `~/.local/bin`; export PATH per shell).
2. `uv sync` — creates `.venv`, installs `python-dotenv`, `google-genai`, `send2trash`.
3. `mkdir -p logs` — REQUIRED before `./src/run_simple_ingest.sh`. Without it
   the wrapper's `mkdir logs/run_simple_ingest.lock` fails and the script
   exits 0 silently (no-op). Fresh clones hit this every time.
4. Write `.env` (see `.env.example`); write `GEMINI_MODEL=...` into `~/.env`.

## Sandbox layout (as snapshotted)

- `VOICE_MEMOS_DIR_0=/home/user/voice-memos`, `VOICE_MEMOS_DIR_1=/home/user/voice-memos/notes`
- Inboxes: `/home/user/voice-memos/notes/`, `/home/user/voice-memos/course/`
- `OBSIDIAN_DAILY_DIR=/home/user/obsidian-daily`
- `~/.env` holds `GEMINI_MODEL=gemini-2.5-flash`
- `.env` holds a dummy `GEMINI_API_KEY` (live transcription fails by design until a real key is provided)

## Verification recipe (what "healthy" means here)

1. `uv run python -m unittest discover -s src -p 'test_*.py'` → 19/19 OK.
2. `uvx ruff check src/transcribe.py src/transcribe_audio.py src/runtime_support.py src/simple_endpoints.py src/test_transcribe_audio.py` → clean.
3. `uv run python -m py_compile src/transcribe.py src/transcribe_audio.py src/runtime_support.py src/simple_endpoints.py` → clean.
4. `uv run siri-transcribe-audio --help` → usage prints.
5. Flow run: drop any-bytes `YYYY-MM-DD HH.MM.SS.m4a` file into the `notes`
   inbox and run `./src/run_simple_ingest.sh`.
   - Dummy key: 3 attempts with exponential backoff, `API_KEY_INVALID` logged
     in `logs/siri_errors.log`, source file retained, exit 1 (honest failure).
   - Real key: bullets appended to `/home/user/obsidian-daily/<date>.md`
     (root body for `notes`, `## Course à Pied` for `course`), source moved
     to Trash, exit 0.

## Gotchas

- Capture filename `YYYY-MM-DD HH.MM.SS.m4a` decides the target daily-note
  date (falls back to file mtime).
- `runtime_support.file_flags` uses BSD `stat -f %Sf`; GNU stat fails → file
  is treated as local. Harmless on Linux, but don't "fix" without reading
  `ensure_local_file`.
- Vault lock path is `~/Library/Caches/com.obsidian.vault-operation.lock`
  (macOS-style, created fine on Linux). `send2trash` on Linux uses
  `~/.local/share/Trash`, not macOS Trash.
- No network-free positive path: live transcription needs the user's real
  `GEMINI_API_KEY` (not in the secrets inventory at onboarding; TODO(confirm)).
- `ffmpeg` absent in sandbox; only the m4a remux fallback needs it.
- launchd scripts (`install_launchd.sh`, `uninstall_launchd.sh`) are
  macOS-only — never run them in the Linux sandbox.
