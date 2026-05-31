#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if pkill -f "[a]pp.main" 2>/dev/null; then
  echo "Bot stopped."
else
  echo "No running bot process found."
fi
