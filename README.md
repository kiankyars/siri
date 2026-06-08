# siri

Transcribes `.m4a` voice memos into Obsidian notes and can also process routed Voice Memos directly from the synced macOS Voice Memos library.

## Behavior

- For each audio file, it generates markdown hyphen bullets.
- It writes into `notes/YYYY-MM-DD.md`:
  - files from the resolved `notes` inbox append into the root body of the daily note
  - files from the resolved `course` inbox append into `## Course`
  - files from the resolved `jl` inbox append into `## JL`
  - if the daily note does not exist, it is created
- `notes` is the catch-all simple inbox for podcasts, books, reading thoughts, and other uncategorized captures.
- After a simple-ingest `.m4a` is successfully appended into the daily note, the source file is moved to macOS Trash.
- Agentic Voice Memos processing:
  - watches the macOS Voice Memos store
  - processes recordings renamed exactly `monde` or `réflexion`
  - reads the original recording directly from the Voice Memos library
  - `monde` writes into `people/{name}.md` under a `## YYYY-MM-DD` section
  - `réflexion` writes into `notes/YYYY-MM-DD.md` under `## <few-word summary> #reflection`
  - leaves source memos in Voice Memos for manual deletion

## Setup

1. Create `.env` from `.env.example` and fill all values.
2. `uv sync`

Required env vars:

- `GEMINI_API_KEY`
- `VOICE_MEMOS_DIR_0`
- `VOICE_MEMOS_DIR_1`
- `OBSIDIAN_DAILY_DIR`

Error logs are written to `logs/siri_errors.log` by default.
Agentic Voice Memos processed-file state is written to `logs/voice_memos_import_state.json`.

## Run manually

- `./src/siri.sh`
- `./src/run_simple_ingest.sh`
- `./src/run_voice_memos_ingest.sh`

## Install launchd watchers

Both LaunchAgents run on the **same machine** (the personal Mac that has access to the iCloud audio sources). The primary (and only needed) command is:

- `./src/install_launchd.sh`
  - Installs/refreshes **both** agents:
    - `com.siri.simple`: watches the resolved `notes`/`course`/`jl` iCloud folders and runs `src/run_simple_ingest.sh`
    - `com.siri.voice-memos`: watches the Voice Memos library and runs `src/run_voice_memos_ingest.sh`

Uninstall:

- `./src/uninstall_launchd.sh`

These are built from the templates `com.siri.simple.plist.template` and `com.siri.voice-memos.plist.template`.
