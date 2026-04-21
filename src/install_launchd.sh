#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SIMPLE_TEMPLATE_PATH="$REPO_DIR/com.siri.simple.plist.template"
VOICE_MEMOS_TEMPLATE_PATH="$REPO_DIR/com.siri.voice-memos.plist.template"
SIMPLE_LABEL="com.siri.simple"
VOICE_MEMOS_LABEL="com.siri.voice-memos"
OLD_LABELS=("com.siri" "com.transcribe")
LOG_DIR="$REPO_DIR/logs"

if [ -f "$REPO_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_DIR/.env"
  set +a
fi
export REPO_DIR
export SIMPLE_LABEL
export VOICE_MEMOS_LABEL

: "${VOICE_MEMOS_DIR_0:?Set VOICE_MEMOS_DIR_0 in .env}"
: "${VOICE_MEMOS_DIR_1:?Set VOICE_MEMOS_DIR_1 in .env}"
: "${OBSIDIAN_DAILY_DIR:?Set OBSIDIAN_DAILY_DIR in .env}"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

python3 - "$SIMPLE_TEMPLATE_PATH" "$VOICE_MEMOS_TEMPLATE_PATH" <<'PY'
from pathlib import Path
import os
import sys

repo = Path(os.environ["REPO_DIR"]).expanduser().resolve()
sys.path.insert(0, str(repo))
from src.simple_endpoints import resolve_simple_endpoint_dirs

simple_template = Path(sys.argv[1]).read_text()
voice_template = Path(sys.argv[2]).read_text()

anchors = (
    Path(os.environ["VOICE_MEMOS_DIR_0"]).expanduser(),
    Path(os.environ["VOICE_MEMOS_DIR_1"]).expanduser(),
)
endpoint_dirs = resolve_simple_endpoint_dirs(*anchors)
voice_memos_library_dir = Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings"
launch_agents_dir = Path.home() / "Library" / "LaunchAgents"

simple_replacements = {
    "__LABEL__": os.environ["SIMPLE_LABEL"],
    "__RUN_SCRIPT__": str((repo / "src" / "run_simple_ingest.sh").resolve()),
    "__WATCH_NOTES__": str(endpoint_dirs["notes"].resolve()),
    "__WATCH_COURSE__": str(endpoint_dirs["course"].resolve()),
    "__WATCH_JL__": str(endpoint_dirs["jl"].resolve()),
    "__WORK_DIR__": str(repo),
    "__STDOUT_LOG__": str((repo / "logs" / "launchd_simple_stdout.log").resolve()),
    "__STDERR_LOG__": str((repo / "logs" / "launchd_simple_stderr.log").resolve()),
}
voice_replacements = {
    "__LABEL__": os.environ["VOICE_MEMOS_LABEL"],
    "__RUN_SCRIPT__": str((repo / "src" / "run_voice_memos_ingest.sh").resolve()),
    "__WATCH_VOICE_MEMOS__": str(voice_memos_library_dir.resolve()),
    "__WORK_DIR__": str(repo),
    "__STDOUT_LOG__": str((repo / "logs" / "launchd_voice_memos_stdout.log").resolve()),
    "__STDERR_LOG__": str((repo / "logs" / "launchd_voice_memos_stderr.log").resolve()),
}

for key, value in simple_replacements.items():
    simple_template = simple_template.replace(key, value)
for key, value in voice_replacements.items():
    voice_template = voice_template.replace(key, value)

(launch_agents_dir / f"{os.environ['SIMPLE_LABEL']}.plist").write_text(simple_template)
(launch_agents_dir / f"{os.environ['VOICE_MEMOS_LABEL']}.plist").write_text(voice_template)
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

for label in "$SIMPLE_LABEL" "$VOICE_MEMOS_LABEL"; do
  bootout_label "$label"
done

for label in "$SIMPLE_LABEL" "$VOICE_MEMOS_LABEL"; do
  bootstrap_label "$label"
done

echo "Installed and started $SIMPLE_LABEL"
echo "plist: $HOME/Library/LaunchAgents/${SIMPLE_LABEL}.plist"
echo "Installed and started $VOICE_MEMOS_LABEL"
echo "plist: $HOME/Library/LaunchAgents/${VOICE_MEMOS_LABEL}.plist"
