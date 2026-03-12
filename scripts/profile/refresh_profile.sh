#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PIPELINE_CONFIG="automation/arxiv-profile-digest.example.toml"
PROFILE_OUTPUT=""
WORKFLOW_NAME="profile-refresh"
SANDBOX_MODE="${SANDBOX_MODE:-read-only}"
ENABLE_NATIVE_SEARCH=0

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/profile/refresh_profile.sh [options]

Options:
  --config <path>        Pipeline TOML config used to resolve the live profile path
  --profile-out <path>   Override the live profile output path
  --workflow <name>      Output directory name for the profile-maintenance report
  --sandbox <mode>       Codex sandbox mode for the profile-maintenance step
  --with-search          Enable native search fallback for the profile-maintenance run
  --help                 Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      PIPELINE_CONFIG="$2"
      shift 2
      ;;
    --profile-out)
      PROFILE_OUTPUT="$2"
      shift 2
      ;;
    --workflow)
      WORKFLOW_NAME="$2"
      shift 2
      ;;
    --sandbox)
      SANDBOX_MODE="$2"
      shift 2
      ;;
    --with-search)
      ENABLE_NATIVE_SEARCH=1
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

resolved_profile_path="$(python3 - "$PIPELINE_CONFIG" "$PROFILE_OUTPUT" <<'PY'
import pathlib
import sys
import tomllib

config_path = pathlib.Path(sys.argv[1])
override = sys.argv[2].strip()
if override:
    print(pathlib.Path(override).expanduser().resolve().as_posix())
else:
    with config_path.open("rb") as fh:
        config = tomllib.load(fh)
    profile_path = pathlib.Path(str(config.get("profile_path") or "profiles/research-interest.json")).expanduser()
    if not profile_path.is_absolute():
        profile_path = (config_path.parent / profile_path).resolve()
    print(profile_path.as_posix())
PY
)"

prompt_file="$(mktemp "${TMPDIR:-/tmp}/profile-refresh.XXXXXX.prompt.txt")"
python3 - "$resolved_profile_path" "$prompt_file" <<'PY'
import pathlib
import sys

target_profile_path = sys.argv[1]
prompt_path = pathlib.Path(sys.argv[2])
template_path = pathlib.Path("automation/prompts/profile-refresh.prompt.txt")

text = template_path.read_text(encoding="utf-8")
text = text.replace("{{TARGET_PROFILE_PATH}}", target_profile_path)
prompt_path.write_text(text, encoding="utf-8")
PY

codex_cmd=(
  bash scripts/core/run_codex_task.sh
  --workflow "$WORKFLOW_NAME"
  --prompt-file "$prompt_file"
  --output-ext json
  --sandbox "$SANDBOX_MODE"
)

if [[ "$ENABLE_NATIVE_SEARCH" != "1" ]]; then
  codex_cmd+=(--no-search)
fi

echo "Step 1/3: refresh live research-interest profile"
profile_output="$(${codex_cmd[@]})"
printf '%s\n' "$profile_output"

profile_report_path="$(printf '%s\n' "$profile_output" | awk -F': ' '/^Done: /{print $2}' | tail -n 1)"
if [[ -z "$profile_report_path" ]]; then
  echo "Failed to resolve generated profile report path" >&2
  exit 2
fi

uv run python - "$profile_report_path" "$resolved_profile_path" <<'PY'
import json
import pathlib
import sys

from codex_research_assist.arxiv_profile_pipeline.profile_contract import normalize_profile_payload

report_path = pathlib.Path(sys.argv[1])
target_path = pathlib.Path(sys.argv[2])
payload = json.loads(report_path.read_text(encoding="utf-8"))
normalized = normalize_profile_payload(payload)
target_path.parent.mkdir(parents=True, exist_ok=True)
target_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
report_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "profile_report_path": report_path.as_posix(),
    "profile_path": target_path.as_posix(),
    "interest_count": len(normalized["interests"]),
}, ensure_ascii=False, indent=2))
PY
