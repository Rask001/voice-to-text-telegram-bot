#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

LABEL="${BOT_LAUNCHD_LABEL:-com.voitext.bot}"
ERR_LOG="$PWD/logs/launchd.err.log"
OUT_LOG="$PWD/logs/launchd.out.log"

processes="$(pgrep -fl "[a]pp.main" 2>/dev/null || true)"
if [ -n "$processes" ]; then
  echo "Bot process found:"
  echo "$processes"
  pid="$(echo "$processes" | awk 'NR==1 {print $1}')"
  echo
  echo "Process resources:"
  ps -o pid,ppid,%cpu,%mem,rss,etime,command -p "$pid" || true
else
  echo "Bot is not running."
fi

echo
echo "launchd service:"
if launchctl list "$LABEL" >/dev/null 2>&1; then
  launchctl list "$LABEL" || true
else
  echo "launchd label '$LABEL' is not loaded."
fi

echo
echo "Logs:"
echo "stdout: $OUT_LOG"
echo "stderr: $ERR_LOG"

if [ -f "$ERR_LOG" ]; then
  echo
  echo "Last stderr lines:"
  tail -30 "$ERR_LOG"
fi

if [ -f "$OUT_LOG" ]; then
  echo
  echo "Last stdout lines:"
  tail -15 "$OUT_LOG"
fi
