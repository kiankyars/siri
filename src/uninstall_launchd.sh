#!/bin/bash
set -euo pipefail

# Uninstall both LaunchAgents and their plists.
# Safe to run even if the agents are not installed.
# This is the primary/only uninstall command.

for label in com.siri.simple com.siri.voice-memos; do
  UID_VALUE="$(id -u)"
  plist="$HOME/Library/LaunchAgents/${label}.plist"

  echo "Unloading $label..."
  launchctl bootout "gui/${UID_VALUE}" "$plist" >/dev/null 2>&1 || true
  launchctl bootout "gui/${UID_VALUE}/${label}" >/dev/null 2>&1 || true

  rm -f "$plist"

  echo "Removed $label (if it was present)."
  echo "plist: $plist (deleted)"
done
