#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKFLOW="skill-task"
PROMPT_FILE="automation/prompts/task.prompt.txt"
OUTPUT_ROOT="reports/generated"
OUTPUT_EXT="md"
SANDBOX_MODE="${SANDBOX_MODE:-read-only}"
ENABLE_NATIVE_SEARCH="${ENABLE_NATIVE_SEARCH:-1}"
CODEX_HOME_DEFAULT="${CODEX_HOME_DEFAULT:-$HOME/.codex}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/core/run_codex_task.sh [options]

Options:
  --workflow <name>       Workflow name used in the report path
  --prompt-file <path>    Prompt file read by `codex exec`
  --output-root <path>    Root directory for generated reports
  --output-ext <ext>      Output file extension (default: md)
  --sandbox <mode>        Codex sandbox mode (default: read-only)
  --no-search             Disable native web search fallback
  --help                  Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workflow)
      WORKFLOW="$2"
      shift 2
      ;;
    --prompt-file)
      PROMPT_FILE="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --output-ext)
      OUTPUT_EXT="$2"
      shift 2
      ;;
    --sandbox)
      SANDBOX_MODE="$2"
      shift 2
      ;;
    --no-search)
      ENABLE_NATIVE_SEARCH=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

cd "$PROJECT_ROOT"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

timestamp="$(date '+%Y-%m-%d-%H%M%S')"
year="$(date '+%Y')"
month="$(date '+%m')"
report_dir="$OUTPUT_ROOT/$WORKFLOW/$year/$month"
report_file="$report_dir/$timestamp.$OUTPUT_EXT"

mkdir -p "$report_dir"

export CODEX_HOME="${CODEX_HOME:-$CODEX_HOME_DEFAULT}"

cmd=(
  codex
  --sandbox "$SANDBOX_MODE"
  --ask-for-approval never
)

if [[ "$ENABLE_NATIVE_SEARCH" == "1" ]]; then
  cmd+=(--search)
fi

cmd+=(
  exec
  --cd "$PROJECT_ROOT"
  --output-last-message "$report_file"
  -
)

echo "Workflow: $WORKFLOW"
echo "Prompt: $PROMPT_FILE"
echo "Report: $report_file"
echo "CODEX_HOME: $CODEX_HOME"

"${cmd[@]}" < "$PROMPT_FILE"

echo "Done: $report_file"
