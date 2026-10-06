# siri

Transcribes `.m4a` files from two configured iCloud inboxes into Obsidian daily notes.

## Behavior

- For each simple-inbox audio file, it generates markdown hyphen bullets.
- Each Gemini request has a two-minute deadline; timed-out attempts are logged and
  use the existing same-model retry path without holding the rest of the queue forever.
- A `429 RESOURCE_EXHAUSTED` response stops the rest of the inbox immediately so
  later files do not burn remaining quota. The LaunchAgent retries hourly in
  addition to WatchPaths, because quota recovery does not create a filesystem event.
- The simple ingest exits nonzero when any capture failed, so launchd's last exit
  code is honest.
- It writes into `notes/YYYY-MM-DD.md`:
  - files from the resolved `notes` inbox append into the root body of the daily note
  - running dictations from the resolved `course` inbox append into `## Course à Pied`
  - if the daily note does not exist, it is created
- `notes` is the catch-all simple inbox for podcasts, books, reading thoughts, and other uncategorized captures.
- After a simple-ingest `.m4a` is successfully appended into the daily note, the source file is moved to the repository's `processed/` folder. Original modification times are preserved; duplicate filenames receive a numeric suffix.
- A daily cron job at 10:00 local time permanently deletes regular `.m4a` files directly in `processed/` whose modification time is more than 30 days old. It skips subdirectories and symlinks. Archive moves and cleanup share a lock.
- Simple note updates use the vault operation lock and atomic replacement. They do not add internal IDs, hashes, or recovery markers to the Markdown. If archiving fails after the note is written, the source remains for retry; a later retry may transcribe and append that capture again.
  - The lock coordinates Siri with the vault synchronizer. External editors do not participate in that advisory lock; the writer rebuilds on changes it detects before replacement, while the synchronizer's settle window provides the broader safety net.
- Siri ingestion never stages, commits, pulls, fetches, merges, rebases, or pushes
  a repository. Repository synchronization belongs to separate vault automation.

## Setup

1. Create `.env` from `.env.example` and fill all values.
2. `uv sync`

Required env vars:

- `GEMINI_API_KEY`
- `VOICE_MEMOS_DIR_0`
- `VOICE_MEMOS_DIR_1`
- `OBSIDIAN_DAILY_DIR`

Set `GEMINI_MODEL` once in `~/.env`; both the inbox flow and single-file helper read it.

Error logs are written to `logs/siri_errors.log` by default.
Cleanup output and errors go to `logs/cleanup_processed.log`.

## Run manually

- `./src/siri.sh`
- `./src/run_simple_ingest.sh`
- `uv run siri-transcribe-audio /path/to/recording.m4a -o /tmp/transcript.txt`
- `uv run python src/processed_audio.py --dry-run`: preview expired processed recordings.
- `uv run python src/processed_audio.py`: permanently delete expired processed recordings.

## Install launchd watchers

The LaunchAgent runs on the Mac that has access to the configured iCloud audio sources. The only installation command needed is:

- `./src/install_launchd.sh`
  - Installs or refreshes `com.siri.simple`, which watches the resolved `notes` and `course` inboxes and runs `src/run_simple_ingest.sh`.
  - Installs the daily cleanup cron job, preserving other crontab entries. Cron runs while the Mac is awake; missed runs wait until the next scheduled day.

Uninstall:

- `./src/uninstall_launchd.sh`

Uninstalling also removes the cleanup cron job; archived recordings remain in `processed/`.

The LaunchAgent is built from `com.siri.simple.plist.template` and invokes `/bin/zsh` explicitly so the background job uses its
Full Disk Access grant when reading iCloud and the Obsidian vault.
