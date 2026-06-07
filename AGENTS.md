# Repository Guidelines

## Project Structure & Module Organization
- Core app logic lives in `src/transcribe.py`.
- Operational scripts are in `src/`:
  - `src/siri.sh` runs both ingestion flows locally.
  - `src/run_simple_ingest.sh` runs the iCloud inbox transcription flow.
  - `src/run_voice_memos_ingest.sh` runs the Voice Memos import flow.
  - `src/install_launchd_simple.sh` installs/refreshes the `com.siri.simple` LaunchAgent (iCloud inboxes).
  - `src/install_launchd_voice_memos.sh` installs/refreshes the `com.siri.voice-memos` LaunchAgent.
  - `src/uninstall_launchd_simple.sh` and `src/uninstall_launchd_voice_memos.sh` remove the respective LaunchAgent.
- Launchd templates are `com.siri.simple.plist.template` and `com.siri.voice-memos.plist.template`.
- Runtime logs are written under `logs/` (e.g. `launchd_simple_*.log`, `launchd_voice_memos_*.log`, `siri_errors.log`).
- Project metadata and dependencies are defined in `pyproject.toml`.

## Build, Test, and Development Commands
- `uv sync`: install/update the virtual environment and dependencies.
- `./src/siri.sh`: run the transcription flow manually.
- `./src/install_launchd_simple.sh`: install and start only the `com.siri.simple` LaunchAgent.
- `./src/install_launchd_voice_memos.sh`: install and start only the `com.siri.voice-memos` LaunchAgent.
- `./src/uninstall_launchd_simple.sh`: remove the simple LaunchAgent.
- `./src/uninstall_launchd_voice_memos.sh`: remove the voice-memos LaunchAgent.
- `uvx ruff check src/transcribe.py`: lint Python code.
- `python3 -m py_compile src/transcribe.py`: quick syntax validation.

## Coding Style & Naming Conventions
- Python 3.10+ with 4-space indentation and type hints where practical.
- Prefer `pathlib.Path` for filesystem paths.
- Environment variables drive runtime configuration:
  - `VOICE_MEMOS_DIR_0`, `VOICE_MEMOS_DIR_1`
  - `OBSIDIAN_DAILY_DIR`
  - `GEMINI_API_KEY`
- Use `ruff` as the formatting/lint quality gate for Python.

## Testing Guidelines
- No formal test suite is currently included.
- Validate changes with:
  1. `uvx ruff check src/transcribe.py`
  2. `python3 -m py_compile src/transcribe.py`
  3. Manual smoke run with a sample `.m4a` in a configured voice memo directory.
- Verify expected output file append behavior and confirm no duplicate processing in the relevant `logs/launchd_*_stderr.log`.

## Commit & Pull Request Guidelines
- Follow concise, imperative commit messages (current history style):
- Prefer one logical change per commit.
- PRs should include:
  - What changed and why
  - Any env/config changes (`.env.example`, launchd behavior)
  - Manual verification steps and log evidence when relevant
