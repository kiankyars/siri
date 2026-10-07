#!/bin/bash
set -euo pipefail

# Install or refresh the ingestion and cleanup LaunchAgents.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SIMPLE_TEMPLATE_PATH="$REPO_DIR/com.siri.simple.plist.template"
CLEANUP_TEMPLATE_PATH="$REPO_DIR/com.siri.cleanup.plist.template"
SIMPLE_LABEL="com.siri.simple"
CLEANUP_LABEL="com.siri.cleanup"
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
export CLEANUP_LABEL

: "${VOICE_MEMOS_DIR_0:?Set VOICE_MEMOS_DIR_0 in .env}"
: "${VOICE_MEMOS_DIR_1:?Set VOICE_MEMOS_DIR_1 in .env}"
: "${OBSIDIAN_DAILY_DIR:?Set OBSIDIAN_DAILY_DIR in .env}"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

if [ ! -x "$REPO_DIR/.venv/bin/python" ]; then
  echo "Run uv sync before installing the LaunchAgents." >&2
  exit 1
fi

python3 - "$SIMPLE_TEMPLATE_PATH" "$CLEANUP_TEMPLATE_PATH" <<'PY'
from pathlib import Path
import os
import sys

repo = Path(os.environ["REPO_DIR"]).expanduser().resolve()
sys.path.insert(0, str(repo))
from src.simple_endpoints import resolve_simple_endpoint_dirs

simple_template = Path(sys.argv[1]).read_text()
cleanup_template = Path(sys.argv[2]).read_text()

anchors = (
    Path(os.environ["VOICE_MEMOS_DIR_0"]).expanduser(),
    Path(os.environ["VOICE_MEMOS_DIR_1"]).expanduser(),
)
endpoint_dirs = resolve_simple_endpoint_dirs(*anchors)

simple_replacements = {
    "__LABEL__": os.environ["SIMPLE_LABEL"],
    "__RUN_SCRIPT__": str((repo / "src" / "run_simple_ingest.sh").resolve()),
    "__WATCH_NOTES__": str(endpoint_dirs["notes"].resolve()),
    "__WATCH_COURSE__": str(endpoint_dirs["course"].resolve()),
    "__WORK_DIR__": str(repo),
    "__STDOUT_LOG__": str((repo / "logs" / "launchd_simple_stdout.log").resolve()),
    "__STDERR_LOG__": str((repo / "logs" / "launchd_simple_stderr.log").resolve()),
}
for key, value in simple_replacements.items():
    simple_template = simple_template.replace(key, value)

(Path.home() / "Library" / "LaunchAgents" / f"{os.environ['SIMPLE_LABEL']}.plist").write_text(simple_template)

cleanup_replacements = {
    "__LABEL__": os.environ["CLEANUP_LABEL"],
    "__PYTHON_BIN__": str(repo / ".venv" / "bin" / "python"),
    "__CLEANUP_SCRIPT__": str(repo / "src" / "processed_audio.py"),
    "__WORK_DIR__": str(repo),
    "__CLEANUP_LOG__": str(repo / "logs" / "cleanup_processed.log"),
}
for key, value in cleanup_replacements.items():
    cleanup_template = cleanup_template.replace(key, value)

(Path.home() / "Library" / "LaunchAgents" / f"{os.environ['CLEANUP_LABEL']}.plist").write_text(cleanup_template)
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

for label in "$SIMPLE_LABEL" "$CLEANUP_LABEL"; do
  bootout_label "$label"
  bootstrap_label "$label"
  echo "Installed and started $label"
  echo "plist: $HOME/Library/LaunchAgents/${label}.plist"
done
