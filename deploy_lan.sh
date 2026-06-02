#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

REMOTE_HOST="${REMOTE_HOST:-192.168.1.104}" \
  ./deploy_common.sh
