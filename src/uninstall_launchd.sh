#!/bin/bash
set -euo pipefail

# Uninstall the ingestion and cleanup LaunchAgents and their plists.
# Safe to run even if the agents are not installed.

UID_VALUE="$(id -u)"
for label in com.siri.simple com.siri.cleanup; do
  plist="$HOME/Library/LaunchAgents/${label}.plist"

  echo "Unloading $label..."
  launchctl bootout "gui/${UID_VALUE}" "$plist" >/dev/null 2>&1 || true
  launchctl bootout "gui/${UID_VALUE}/${label}" >/dev/null 2>&1 || true

  rm -f "$plist"

  echo "Removed $label (if it was present)."
  echo "plist: $plist (deleted)"
done
