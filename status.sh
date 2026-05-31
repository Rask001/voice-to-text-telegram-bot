#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

processes="$(pgrep -fl "[a]pp.main" 2>/dev/null || true)"
if [ -n "$processes" ]; then
  echo "Bot process found:"
  echo "$processes"
  exit 0
fi

echo "Bot is not running."
