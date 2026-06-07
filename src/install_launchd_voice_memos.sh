#!/bin/bash
set -euo pipefail

# Install/refresh ONLY the com.siri.voice-memos LaunchAgent.
# This watches the Apple Voice Memos shared recordings directory
# and runs src/run_voice_memos_ingest.sh on new/changed memos.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VOICE_TEMPLATE_PATH="$REPO_DIR/com.siri.voice-memos.plist.template"
VOICE_MEMOS_LABEL="com.siri.voice-memos"
OLD_LABELS=("com.siri" "com.transcribe")
LOG_DIR="$REPO_DIR/logs"

if [ -f "$REPO_DIR/.env" ]; then
  set -a
  # shellcheck disable:SC1091
  source "$REPO_DIR/.env"
  set +a
fi

export REPO_DIR
export VOICE_MEMOS_LABEL

# Note: VOICE_MEMOS_DIR_0 / VOICE_MEMOS_DIR_1 are not required for the
# voice-memos watcher (it hardcodes the Group Containers path).
# They are only used by the "simple" endpoint resolver.
: "${OBSIDIAN_DAILY_DIR:?Set OBSIDIAN_DAILY_DIR in .env}"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

python3 - "$VOICE_TEMPLATE_PATH" <<'PY'
from pathlib import Path
import os
import sys

repo = Path(os.environ["REPO_DIR"]).expanduser().resolve()

voice_template = Path(sys.argv[1]).read_text()

voice_memos_library_dir = Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings"

voice_replacements = {
    "__LABEL__": os.environ["VOICE_MEMOS_LABEL"],
    "__RUN_SCRIPT__": str((repo / "src" / "run_voice_memos_ingest.sh").resolve()),
    "__WATCH_VOICE_MEMOS__": str(voice_memos_library_dir.resolve()),
    "__WORK_DIR__": str(repo),
    "__STDOUT_LOG__": str((repo / "logs" / "launchd_voice_memos_stdout.log").resolve()),
    "__STDERR_LOG__": str((repo / "logs" / "launchd_voice_memos_stderr.log").resolve()),
}

for key, value in voice_replacements.items():
    voice_template = voice_template.replace(key, value)

( Path.home() / "Library" / "LaunchAgents" / f"{os.environ['VOICE_MEMOS_LABEL']}.plist" ).write_text(voice_template)
PY

UID_VALUE="$(id -u)"

bootout_label() {
  local label="$1"
  local target="gui/${UID_VALUE}/${label}"
  local plist="$HOME/Library/LaunchAgents/${label}.plist"
  launchctl bootout "gui/${UID_VALUE}" "$plist" >/dev/null 2>&1 || true
  launchctl bootout "$target" >/dev/null 2>&1 || true
}

bootstrap_label() {
  local label="$1"
  local target="gui/${UID_VALUE}/${label}"
  local plist="$HOME/Library/LaunchAgents/${label}.plist"
  launchctl bootstrap "gui/${UID_VALUE}" "$plist"
  launchctl enable "$target"
  launchctl kickstart -k "$target"
}

for old_label in "${OLD_LABELS[@]}"; do
  bootout_label "$old_label"
  rm -f "$HOME/Library/LaunchAgents/${old_label}.plist"
done

bootout_label "$VOICE_MEMOS_LABEL"
bootstrap_label "$VOICE_MEMOS_LABEL"

echo "Installed and started $VOICE_MEMOS_LABEL"
echo "plist: $HOME/Library/LaunchAgents/${VOICE_MEMOS_LABEL}.plist"
