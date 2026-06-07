#!/bin/bash
set -euo pipefail

# Combined entry point to uninstall both LaunchAgents.
# Mirrors install_launchd.sh.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Uninstalling com.siri.simple"
"$SCRIPT_DIR/uninstall_launchd_simple.sh"

echo
echo "==> Uninstalling com.siri.voice-memos"
"$SCRIPT_DIR/uninstall_launchd_voice_memos.sh"

echo
echo "Both LaunchAgents uninstalled (if they were present)."
