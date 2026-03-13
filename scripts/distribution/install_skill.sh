#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="research-assist"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${1:-$HOME/.openclaw/skills/$SKILL_NAME}"
RUN_SYNC="${RUN_UV_SYNC:-1}"

copy_dir() {
  local rel="$1"
  mkdir -p "$TARGET_ROOT/$rel"
  cp -a "$SCRIPT_DIR/$rel/." "$TARGET_ROOT/$rel/"
}

copy_file() {
  local rel="$1"
  mkdir -p "$(dirname "$TARGET_ROOT/$rel")"
  cp -f "$SCRIPT_DIR/$rel" "$TARGET_ROOT/$rel"
}

mkdir -p "$TARGET_ROOT"

copy_file "SKILL.md"
copy_file "config.example.json"
copy_file "pyproject.toml"
copy_file "uv.lock"
copy_dir "src"
copy_dir "references"
copy_dir "automation"
copy_dir "reports"
copy_dir "profiles"

mkdir -p "$TARGET_ROOT/profiles" "$TARGET_ROOT/reports"

if [[ ! -f "$TARGET_ROOT/config.json" ]]; then
  cp "$TARGET_ROOT/config.example.json" "$TARGET_ROOT/config.json"
fi

if [[ ! -f "$TARGET_ROOT/profiles/research-interest.json" ]]; then
  cp "$TARGET_ROOT/profiles/research-interest.example.json" \
    "$TARGET_ROOT/profiles/research-interest.json"
fi

if [[ "$RUN_SYNC" != "0" ]] && command -v uv >/dev/null 2>&1; then
  (
    cd "$TARGET_ROOT"
    uv sync
  )
fi

echo "Installed $SKILL_NAME to $TARGET_ROOT"
