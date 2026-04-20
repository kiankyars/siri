#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_PATH="$REPO_DIR/com.siri.plist.template"
LABEL="com.siri"
OLD_LABEL="com.transcribe"
PLIST_OUT="$HOME/Library/LaunchAgents/${LABEL}.plist"
OLD_PLIST_OUT="$HOME/Library/LaunchAgents/${OLD_LABEL}.plist"
LOG_DIR="$REPO_DIR/logs"

if [ -f "$REPO_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_DIR/.env"
  set +a
fi
export REPO_DIR
export LABEL

: "${VOICE_MEMOS_DIR_0:?Set VOICE_MEMOS_DIR_0 in .env}"
: "${VOICE_MEMOS_DIR_1:?Set VOICE_MEMOS_DIR_1 in .env}"
: "${OBSIDIAN_DAILY_DIR:?Set OBSIDIAN_DAILY_DIR in .env}"

mkdir -p "$(dirname "$PLIST_OUT")" "$LOG_DIR"

python3 - "$TEMPLATE_PATH" "$PLIST_OUT" <<'PY'
from pathlib import Path
import os
import sys

template = Path(sys.argv[1]).read_text()
repo = Path(os.environ["REPO_DIR"]).expanduser().resolve()
sys.path.insert(0, str(repo))
from src.simple_endpoints import resolve_simple_endpoint_dirs

run_script = str((repo / "src" / "siri.sh").resolve())
anchors = (
    Path(os.environ["VOICE_MEMOS_DIR_0"]).expanduser(),
    Path(os.environ["VOICE_MEMOS_DIR_1"]).expanduser(),
)
endpoint_dirs = resolve_simple_endpoint_dirs(*anchors)
voice_memos_library_dir = Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings"
replacements = {
    "__LABEL__": os.environ["LABEL"],
    "__RUN_SCRIPT__": run_script,
    "__WATCH_NOTES__": str(endpoint_dirs["notes"].resolve()),
    "__WATCH_COURSE__": str(endpoint_dirs["course"].resolve()),
    "__WATCH_JL__": str(endpoint_dirs["jl"].resolve()),
    "__WATCH_VOICE_MEMOS__": str(voice_memos_library_dir.resolve()),
    "__WORK_DIR__": str(repo),
    "__STDOUT_LOG__": str((repo / "logs" / "launchd_stdout.log").resolve()),
    "__STDERR_LOG__": str((repo / "logs" / "launchd_stderr.log").resolve()),
}
for key, value in replacements.items():
    template = template.replace(key, value)
Path(sys.argv[2]).write_text(template)
PY

UID_VALUE="$(id -u)"
TARGET="gui/${UID_VALUE}/${LABEL}"
OLD_TARGET="gui/${UID_VALUE}/${OLD_LABEL}"

launchctl bootout "gui/${UID_VALUE}" "$OLD_PLIST_OUT" >/dev/null 2>&1 || true
launchctl bootout "$OLD_TARGET" >/dev/null 2>&1 || true
if [ -f "$OLD_PLIST_OUT" ] && [ "$OLD_PLIST_OUT" != "$PLIST_OUT" ]; then
  rm -f "$OLD_PLIST_OUT"
fi
launchctl bootout "gui/${UID_VALUE}" "$PLIST_OUT" >/dev/null 2>&1 || true
launchctl bootout "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID_VALUE}" "$PLIST_OUT"
launchctl enable "$TARGET"
launchctl kickstart -k "$TARGET"

echo "Installed and started $LABEL"
echo "plist: $PLIST_OUT"
