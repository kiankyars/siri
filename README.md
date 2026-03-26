# siri

Transcribes `.m4a` voice memos from two watch folders into daily Obsidian markdown files.

## Behavior

- For each audio file, it generates markdown hyphen bullets.
- It writes into `notes/YYYY-MM-DD.md`:
  - files from `VOICE_MEMOS_DIR_0` append into the root body of the daily note
  - files from `VOICE_MEMOS_DIR_1` append into `## Course`
  - if the daily note does not exist, it is created
- Processed audio files are moved to Trash.

## Setup

1. Create `.env` from `.env.example` and fill all values.
2. `uv sync`

Required env vars:

- `GEMINI_API_KEY`
- `VOICE_MEMOS_DIR_0`
- `VOICE_MEMOS_DIR_1`
- `OBSIDIAN_DAILY_DIR`

Error logs are written to `logs/siri_errors.log` by default.

## Run manually

- `./src/run_siri.sh`

## Install launchd watcher

- `./src/install_launchd.sh`

This installs `~/Library/LaunchAgents/com.siri.plist` from the repo template and watches:

- `VOICE_MEMOS_DIR_0`
- `VOICE_MEMOS_DIR_1`
