#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

REMOTE_HOST="${REMOTE_HOST:?REMOTE_HOST is required}"
REMOTE_USER="${REMOTE_USER:-niki4ka}"
REMOTE_KEY="${REMOTE_KEY:-$HOME/.ssh/codex_remote_mac}"
REMOTE_PROJECT_DIR="${REMOTE_PROJECT_DIR:-~/Projects/voice-to-text-telegram-bot}"
REMOTE_SSH_OPTS="${REMOTE_SSH_OPTS:--o ConnectTimeout=12 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new}"

echo "Deploy target: $REMOTE_USER@$REMOTE_HOST"
echo "Remote project: $REMOTE_PROJECT_DIR"
echo

if [ ! -d .git ]; then
  echo "This directory is not a git repository."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Python venv not found: .venv/bin/python"
  echo "Create it first and install requirements."
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "Current branch is '$CURRENT_BRANCH', but the server deploy pulls 'main'."
  echo "Switch to main before running this script."
  exit 1
fi

echo "Local git status:"
git status --short
echo

read -r -p "Commit message: " COMMIT_MESSAGE
if [ -z "${COMMIT_MESSAGE// }" ]; then
  echo "Commit message is empty. Aborting."
  exit 1
fi

echo
echo "Running local checks..."
.venv/bin/python -m compileall app tests
.venv/bin/python -m unittest discover -s tests

echo
echo "Staging changes..."
git add .

if git diff --cached --quiet; then
  echo "No staged changes. Skipping commit and push."
else
  echo "Creating commit..."
  git commit -m "$COMMIT_MESSAGE"

  echo
  echo "Pushing to GitHub: origin main"
  git push origin main
fi

echo
echo "Updating server..."
ssh -i "$REMOTE_KEY" $REMOTE_SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" \
  "cd $REMOTE_PROJECT_DIR && ./deploy.sh && ./status.sh"

echo
echo "Done."
