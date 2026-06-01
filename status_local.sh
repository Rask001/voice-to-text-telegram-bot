#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE_PATH="${ENV_FILE:-.env.local}"
PID_FILE="data/local_bot.pid"
OUT_LOG="logs/local.out.log"
ERR_LOG="logs/local.err.log"

get_command() {
  ps -p "$1" -o command= 2>/dev/null || true
}

is_bot_command() {
  command="$1"
  echo "$command" | grep -qi "python" && echo "$command" | grep -q "app.main"
}

process_cwd() {
  lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true
}

find_local_bot_pid() {
  pids="$(pgrep -f "[a]pp.main" 2>/dev/null || true)"
  for found_pid in $pids; do
    command="$(get_command "$found_pid")"
    [ -n "$command" ] || continue
    is_bot_command "$command" || continue
    cwd="$(process_cwd "$found_pid")"
    if [ -z "$cwd" ] || [ "$cwd" = "$PWD" ]; then
      echo "$found_pid"
      break
    fi
  done
}

echo "Local TEST BOT status"
echo "ENV_FILE: $ENV_FILE_PATH"

if [ -f "$ENV_FILE_PATH" ]; then
  database_url="$(grep -E '^DATABASE_URL=' "$ENV_FILE_PATH" | cut -d= -f2- || true)"
  echo "DATABASE_URL: ${database_url:-not set}"
else
  echo "ENV file not found."
fi

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE")"
  command="$(get_command "$pid")"
  if [ -n "$command" ] && is_bot_command "$command"; then
    echo "Status: running"
    echo "PID: $pid"
    echo
    ps -o pid,ppid,%cpu,%mem,rss,etime,command -p "$pid" || true
  else
    fallback_pid="$(find_local_bot_pid)"
    if [ -n "$fallback_pid" ]; then
      echo "Status: running without valid pid file"
      echo "PID: $fallback_pid"
      echo
      ps -o pid,ppid,%cpu,%mem,rss,etime,command -p "$fallback_pid" || true
    else
      echo "Status: stopped (removed stale pid file)"
      rm -f "$PID_FILE"
    fi
  fi
else
  fallback_pid="$(find_local_bot_pid)"
  if [ -n "$fallback_pid" ]; then
    echo "Status: running without pid file"
    echo "PID: $fallback_pid"
    echo
    ps -o pid,ppid,%cpu,%mem,rss,etime,command -p "$fallback_pid" || true
  else
    echo "Status: stopped"
  fi
fi

echo
echo "Logs:"
echo "stdout: $OUT_LOG"
echo "stderr: $ERR_LOG"

if [ -f "$ERR_LOG" ]; then
  echo
  echo "Last stderr lines:"
  tail -20 "$ERR_LOG"
fi

if [ -f "$OUT_LOG" ]; then
  echo
  echo "Last stdout lines:"
  tail -20 "$OUT_LOG"
fi
