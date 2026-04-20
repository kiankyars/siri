# Repository Guidelines

## Project Structure & Module Organization
- Core app logic lives in `src/transcribe.py`.
- Operational scripts are in `src/`:
  - `src/siri.sh` runs the transcription job locally.
  - `src/install_launchd.sh` installs/refreshes the launchd agent.
- Launchd template is `com.siri.plist.template`.
- Runtime logs are written under `logs/` (`launchd_stdout.log`, `launchd_stderr.log`, `siri_errors.log`).
- Project metadata and dependencies are defined in `pyproject.toml`.

## Build, Test, and Development Commands
- `uv sync`: install/update the virtual environment and dependencies.
- `./src/siri.sh`: run the transcription flow manually.
- `./src/install_launchd.sh`: install and start `com.siri` LaunchAgent.
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
- Verify expected output file append behavior and confirm no duplicate processing in `logs/launchd_stderr.log`.

## Commit & Pull Request Guidelines
- Follow concise, imperative commit messages (current history style):
- Prefer one logical change per commit.
- PRs should include:
  - What changed and why
  - Any env/config changes (`.env.example`, launchd behavior)
  - Manual verification steps and log evidence when relevant
