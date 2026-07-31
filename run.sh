#!/usr/bin/env bash
# Start de DaKanAI interviewserver
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
set -a
source .env
set +a

exec .venv/bin/python -m server.app
