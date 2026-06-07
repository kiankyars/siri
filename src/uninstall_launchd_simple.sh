#!/bin/bash
set -euo pipefail

# Uninstall ONLY the com.siri.simple LaunchAgent and its plist.
# Safe to run even if the agent is not installed.

LABEL="com.siri.simple"
UID_VALUE="$(id -u)"
plist="$HOME/Library/LaunchAgents/${LABEL}.plist"

echo "Unloading $LABEL..."
launchctl bootout "gui/${UID_VALUE}" "$plist" >/dev/null 2>&1 || true
launchctl bootout "gui/${UID_VALUE}/${LABEL}" >/dev/null 2>&1 || true

rm -f "$plist"

echo "Removed $LABEL (if it was present)."
echo "plist: $plist (deleted)"
