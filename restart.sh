#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

LABEL="${BOT_LAUNCHD_LABEL:-com.voitext.bot}"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ -f "$PLIST" ]; then
  if launchctl list "$LABEL" >/dev/null 2>&1; then
    launchctl kickstart -k "$DOMAIN/$LABEL"
  else
    launchctl bootstrap "$DOMAIN" "$PLIST"
  fi
  sleep 2
  ./status.sh
  exit 0
fi

./stop.sh || true
sleep 1
./start.sh
