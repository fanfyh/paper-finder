#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CONFIG_PATH="${REPO_ROOT}/temp/real-zotero/config.local.json"

if [[ $# -ge 2 && "$1" == "--config" ]]; then
  CONFIG_PATH="$2"
  shift 2
fi

cd "$REPO_ROOT"
uv run python scripts/repro/real_zotero_flow.py --config "$CONFIG_PATH" "$@"
