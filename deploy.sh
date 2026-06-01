#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt

./restart.sh
