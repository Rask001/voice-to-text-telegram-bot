#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

existing_pid="$(pgrep -f "[a]pp.main" 2>/dev/null | head -n 1 || true)"
if [ -n "$existing_pid" ]; then
  echo "Bot is already running. PID: $existing_pid"
  exit 0
fi

echo "Starting bot. Press Ctrl+C to stop."
exec .venv/bin/python -m app.main
