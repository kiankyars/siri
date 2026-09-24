# siri — Agent Guidance

Repo: `kiankyars/siri` (default branch: `main`)

Transcribes `.m4a` recordings from two configured iCloud inboxes into Obsidian
daily notes using Gemini: markdown bullets are appended to the daily note
(root body for the `notes` inbox, `## Course à Pied` for the `course` inbox),
then the source file is moved to macOS Trash. Single CLI app — no web server,
no database, no Docker/Compose. launchd watcher is macOS-only.

## Stack

- Python 3.10+ (onboarding verified on 3.13.x), 4-space indent, type hints, `pathlib`.
- Package manager: `uv` (PEP 621 `pyproject.toml`, hatchling build backend).
- Dependencies: `python-dotenv`, `google-genai`, `send2trash`.
- Console scripts: `siri` → `src.transcribe:main`, `siri-transcribe-audio` → `src.transcribe_audio:main`.

## Commands

| Purpose | Command |
|---|---|
| Install/sync dependencies | `uv sync` |
| Run inbox ingest (both inboxes) | `./src/run_simple_ingest.sh` (alias: `./src/siri.sh`) |
| Transcribe one file | `uv run siri-transcribe-audio /path/to/rec.m4a -o /tmp/out.txt` |
| Unit tests | `uv run python -m unittest discover -s src -p 'test_*.py'` |
| Lint (quality gate) | `uvx ruff check src/transcribe.py src/transcribe_audio.py src/runtime_support.py src/simple_endpoints.py src/test_transcribe_audio.py` |
| Syntax check | `uv run python -m py_compile src/transcribe.py src/transcribe_audio.py src/runtime_support.py src/simple_endpoints.py` |
| Install launchd watcher (macOS only) | `./src/install_launchd.sh` |
| Uninstall launchd watcher (macOS only) | `./src/uninstall_launchd.sh` |

Quirk: `run_simple_ingest.sh` silently exits 0 and does nothing if `logs/`
does not exist (its lock-dir `mkdir` fails). Fresh clones must run
`mkdir -p logs` once before using the wrapper. TODO(confirm): flag to the
owner — this is arguably a repo bug.

## Environment

Create `.env` from `.env.example`:

| Var | Meaning | Sandbox value |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API key; a real key is required for live transcription | dummy value — live calls fail with 400 `API_KEY_INVALID`. TODO(confirm): real key not in secrets inventory |
| `VOICE_MEMOS_DIR_0` | anchor dir for `notes`/`course` inbox resolution | `/home/user/voice-memos` |
| `VOICE_MEMOS_DIR_1` | second anchor dir | `/home/user/voice-memos/notes` |
| `OBSIDIAN_DAILY_DIR` | Obsidian daily-notes directory | `/home/user/obsidian-daily` |

- `GEMINI_MODEL` is read from `~/.env` (sandbox: `gemini-2.5-flash`); optional fallback key `GEMINI_API_KEY_2`.
- iCloud/macOS specifics (dataless-file download via `brctl`, `stat -f` flags,
  send2trash → macOS Trash, Full Disk Access, launchd) degrade gracefully or
  do not apply in the Linux sandbox; inbox dirs are plain local dirs there.

## Codebase map (inlined — tiny repo, one top-level dir)

| Path | Role |
|---|---|
| `src/transcribe.py` | Entry `siri` — inbox flow: config, Gemini bullet generation (2-min deadline, retries, 429 quota stop), atomic note writes, Trash |
| `src/simple_endpoints.py` | Resolves `notes` / `course` inbox dirs from anchor paths; defines `## Course à Pied` heading |
| `src/transcribe_audio.py` | Entry `siri-transcribe-audio` — single-file Gemini transcription, upload-state polling, m4a remux fallback |
| `src/runtime_support.py` | Env helpers (with `~/.env` fallback), error logging, kernel-held vault operation lock, iCloud dataless-file handling |
| `src/siri.sh`, `src/run_simple_ingest.sh` | Wrappers: source `.env`, lock dir under `logs/`, run `src/transcribe.py` with `.venv` python |
| `src/test_transcribe_audio.py` | 19 unit tests with mocked Gemini client (no network) |
| `src/install_launchd.sh`, `src/uninstall_launchd.sh`, `com.siri.simple.plist.template` | macOS LaunchAgent install/uninstall and template |
| `pyproject.toml`, `.env.example` | Project metadata, dependencies, console scripts, env template |
| `logs/` (gitignored) | Runtime + error logs (`siri_errors.log`, `launchd_simple_*.log`) |

Runtime boundaries (from `AGENTS.md` — must preserve):
- Ingestion never stages, commits, pulls, fetches, merges, rebases, or pushes a repository.
- Vault writes use the shared kernel-held vault operation lock and atomic replacement; no ingestion IDs, hashes, or recovery markers in notes.
- `ruff` is the formatting/lint quality gate.

## Local verification

Performed at onboarding (2026-09-24) in the sandbox; re-run on demand:

1. `uv sync` — dependencies installed into `.venv` (uv 0.12.18, Python 3.13.14).
2. Unit tests: 19/19 OK (`uv run python -m unittest discover -s src -p 'test_*.py'`).
3. `uvx ruff check <all five src modules>` — all checks passed.
4. `py_compile` on the five modules — clean.
5. `uv run siri-transcribe-audio --help` — usage prints correctly.
6. Primary-flow exercise: dummy capture `2026-09-24 12.00.00.m4a` in the
   `notes` inbox, `./src/run_simple_ingest.sh` → endpoints resolved, three
   Gemini attempts with backoff (dummy key rejected `API_KEY_INVALID`),
   failure logged to `logs/siri_errors.log`, source retained for retry, exit
   code 1. Positive note-writing path is covered by the mocked unit tests.
   Live transcription requires the user's real `GEMINI_API_KEY` — TODO(confirm).

Validation Summary: dev stack healthy (CLI app; no services to provision);
all repo-declared quality gates pass; primary flow exercised to the external
API boundary; only external gap is the real Gemini API key.

## Sandbox snapshot

- Snapshot ID: `qo0bjpv3g6dhhtc2k7ll:default`
- Captured: 2026-09-24T20:47:38.544Z (ISO-8601)
- State: `.venv` synced; `.env` and `~/.env` written; dummy inboxes at
  `/home/user/voice-memos/{notes,course}`; daily dir at `/home/user/obsidian-daily`;
  `logs/` created; demo capture left in the notes inbox.

## Known limitations

- `ffmpeg` is not installed in the sandbox (only needed for the m4a
  INVALID_ARGUMENT remux fallback in `transcribe_audio.py`).
- launchd install/uninstall must never be run in the Linux sandbox.
