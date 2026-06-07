#!/bin/bash
set -euo pipefail

# Combined entry point for both LaunchAgents.
# Use this when you want to install/refresh *both* the simple (iCloud folder watcher)
# and voice-memos agents on the same machine (current setup: both on personal Mac).
#
# The per-agent scripts (install_launchd_simple.sh / install_launchd_voice_memos.sh)
# are still available if you ever want to manage them independently.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing com.siri.simple"
"$SCRIPT_DIR/install_launchd_simple.sh"

echo
echo "==> Installing com.siri.voice-memos"
"$SCRIPT_DIR/install_launchd_voice_memos.sh"

echo
echo "Both LaunchAgents installed/refreshed."
