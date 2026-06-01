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

if [ "$ENV_FILE_PATH" != ".env.local" ]; then
  echo "Refusing to start local test bot with ENV_FILE=$ENV_FILE_PATH"
  echo "Use ENV_FILE=.env.local for local testing."
  exit 1
fi

if [ ! -f "$ENV_FILE_PATH" ]; then
  echo "$ENV_FILE_PATH not found. Create it from .env.example and use the test bot token."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo ".venv/bin/python not found. Create venv and install requirements first."
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE_PATH"
set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN is missing in $ENV_FILE_PATH"
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is missing in $ENV_FILE_PATH"
  exit 1
fi

if [ -f ".env" ]; then
  production_token="$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2- || true)"
  if [ -n "$production_token" ] && [ "$TELEGRAM_BOT_TOKEN" = "$production_token" ]; then
    echo "Refusing to start: .env.local uses the same Telegram token as .env."
    echo "Create a separate test bot token in BotFather."
    exit 1
  fi
fi

case "$DATABASE_URL" in
  *bot_local_test.db*) ;;
  *)
    echo "Refusing to start: local DATABASE_URL must point to bot_local_test.db"
    echo "Current DATABASE_URL: $DATABASE_URL"
    exit 1
    ;;
esac

mkdir -p data logs

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE")"
  old_command="$(get_command "$old_pid")"
  if [ -n "$old_command" ] && is_bot_command "$old_command"; then
    echo "Local TEST BOT is already running. PID: $old_pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

existing_pid="$(find_local_bot_pid)"
if [ -n "$existing_pid" ]; then
  echo "Local TEST BOT is already running without pid file. PID: $existing_pid"
  echo "$existing_pid" > "$PID_FILE"
  exit 0
fi

token_len="${#TELEGRAM_BOT_TOKEN}"
if [ "$token_len" -gt 4 ]; then
  token_suffix="${TELEGRAM_BOT_TOKEN:$((token_len - 4))}"
else
  token_suffix="$TELEGRAM_BOT_TOKEN"
fi

echo "Starting LOCAL TEST BOT"
echo "ENV_FILE: $ENV_FILE_PATH"
echo "DATABASE_URL: $DATABASE_URL"
echo "TELEGRAM_BOT_TOKEN suffix: ****$token_suffix"
echo "stdout: $OUT_LOG"
echo "stderr: $ERR_LOG"

nohup env ENV_FILE="$ENV_FILE_PATH" APP_ENV=local .venv/bin/python -m app.main \
  > "$OUT_LOG" 2> "$ERR_LOG" &

pid="$!"
echo "$pid" > "$PID_FILE"
sleep 2

if kill -0 "$pid" 2>/dev/null; then
  echo "Local TEST BOT started. PID: $pid"
else
  echo "Local TEST BOT failed to start. Check $ERR_LOG"
  rm -f "$PID_FILE"
  exit 1
fi
