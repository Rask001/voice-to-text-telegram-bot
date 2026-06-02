#!/bin/bash
set -euo pipefail

# Fix only the route to the server's Tailscale IP.
# Hupp/VPN stays enabled; this script does not touch default routes.

TARGET_TAILSCALE_IP="${TARGET_TAILSCALE_IP:-100.104.17.90}"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale CLI not found."
  exit 1
fi

LOCAL_TAILSCALE_IP="$(tailscale ip -4 2>/dev/null | head -n 1 | tr -d '[:space:]')"
if [ -z "$LOCAL_TAILSCALE_IP" ]; then
  echo "Could not detect local Tailscale IP. Is Tailscale running?"
  exit 1
fi

TAILSCALE_INTERFACE="$(
  ifconfig \
    | awk -v ip="$LOCAL_TAILSCALE_IP" '
        /^[a-z0-9]+:/ { iface=$1; sub(":", "", iface) }
        $0 ~ "inet " ip " " { print iface; exit }
      '
)"

if [ -z "$TAILSCALE_INTERFACE" ]; then
  echo "Could not detect Tailscale interface for $LOCAL_TAILSCALE_IP."
  exit 1
fi

echo "Local Tailscale IP: $LOCAL_TAILSCALE_IP"
echo "Tailscale interface: $TAILSCALE_INTERFACE"
echo "Target server IP: $TARGET_TAILSCALE_IP"

sudo route -n delete -host "$TARGET_TAILSCALE_IP" 2>/dev/null || true
sudo route -n add -host "$TARGET_TAILSCALE_IP" -interface "$TAILSCALE_INTERFACE"

echo
echo "Route after fix:"
route -n get "$TARGET_TAILSCALE_IP"

echo
echo "Done. Hupp/VPN was not disabled or restarted."
