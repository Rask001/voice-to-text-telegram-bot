#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

REMOTE_HOST="${REMOTE_HOST:-100.104.17.90}"
REMOTE_USER="${REMOTE_USER:-niki4ka}"
REMOTE_KEY="${REMOTE_KEY:-$HOME/.ssh/codex_remote_mac}"

echo "Checking Tailscale SSH route to $REMOTE_HOST..."
if ! ssh -i "$REMOTE_KEY" -o BatchMode=yes -o ConnectTimeout=8 "$REMOTE_USER@$REMOTE_HOST" "echo ok" >/dev/null 2>&1; then
  echo "Tailscale SSH did not answer quickly. Trying to fix only the host route."
  if [ -x ./fix_tailscale_route.sh ]; then
    TARGET_TAILSCALE_IP="$REMOTE_HOST" ./fix_tailscale_route.sh
  else
    echo "fix_tailscale_route.sh not found or not executable."
    exit 1
  fi
fi

REMOTE_HOST="$REMOTE_HOST" \
REMOTE_USER="$REMOTE_USER" \
REMOTE_KEY="$REMOTE_KEY" \
REMOTE_SSH_OPTS="${REMOTE_SSH_OPTS:--o ConnectTimeout=12 -o ServerAliveInterval=15 -o ServerAliveCountMax=3}" \
  ./deploy_common.sh
