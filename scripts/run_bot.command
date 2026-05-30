#!/bin/zsh
cd "$(dirname "$0")/.."
eval "$(/opt/homebrew/bin/brew shellenv)"
.venv/bin/python -m app.main
echo
echo "Bot process stopped. You can close this window."
read -k 1 "?Press any key to close..."
