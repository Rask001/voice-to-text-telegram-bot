#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

PID_FILE="data/local_bot.pid"

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

find_fallback_pid() {
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

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE")"
else
  pid="$(find_fallback_pid)"
  if [ -z "$pid" ]; then
    echo "No local TEST BOT process found."
    exit 0
  fi
  echo "No pid file found, but found bot process by app.main. PID: $pid"
fi

command="$(get_command "$pid")"

if [ -z "$command" ]; then
  fallback_pid="$(find_fallback_pid)"
  if [ -z "$fallback_pid" ]; then
    echo "Local TEST BOT process is not running. Removing stale pid file."
    rm -f "$PID_FILE"
    exit 0
  fi
  pid="$fallback_pid"
  command="$(get_command "$pid")"
  echo "Pid file was stale, but found bot process by app.main. PID: $pid"
fi

if [ -z "$command" ]; then
  echo "Could not inspect bot process. Removing stale pid file."
  rm -f "$PID_FILE"
  exit 0
fi

if ! echo "$command" | grep -qi "python"; then
  echo "PID $pid is not a Python process. Not stopping it."
  echo "Command: $command"
  exit 1
fi

if ! echo "$command" | grep -q "app.main"; then
  echo "PID $pid is not the local bot process. Not stopping it."
  echo "Command: $command"
  exit 1
fi

kill "$pid"

for _ in 1 2 3 4 5; do
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "Local TEST BOT stopped."
    exit 0
  fi
  sleep 1
done

if kill -TERM "$pid" 2>/dev/null; then
  sleep 1
fi

if kill -0 "$pid" 2>/dev/null; then
  echo "Local TEST BOT did not stop yet. Check manually: ps -p $pid"
else
  rm -f "$PID_FILE"
  echo "Local TEST BOT stopped."
fi
