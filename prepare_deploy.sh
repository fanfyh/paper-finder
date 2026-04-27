#!/usr/bin/env bash
set -euo pipefail

# Override this if needed. When left unchanged, the script uses its own location.
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}"
DEPLOY_MODE_FILE=".deploy_mode"
DEFAULT_DEPLOY_MODE="local"

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "ERROR: PROJECT_DIR does not exist: $PROJECT_DIR" >&2
    exit 1
fi

if [[ ! -f "$PROJECT_DIR/src/codex_research_assist/openclaw_runner.py" ]]; then
    echo "ERROR: openclaw_runner.py not found under PROJECT_DIR: $PROJECT_DIR" >&2
    exit 1
fi

DEPLOY_MODE="${DEPLOY_MODE:-}"
if [[ -z "$DEPLOY_MODE" && -f "$PROJECT_DIR/$DEPLOY_MODE_FILE" ]]; then
    DEPLOY_MODE="$(tr -d '[:space:]' < "$PROJECT_DIR/$DEPLOY_MODE_FILE")"
fi
DEPLOY_MODE="${DEPLOY_MODE:-$DEFAULT_DEPLOY_MODE}"

if [[ "$DEPLOY_MODE" != "local" && "$DEPLOY_MODE" != "pages" ]]; then
    echo "ERROR: DEPLOY_MODE must be 'local' or 'pages', got: $DEPLOY_MODE" >&2
    exit 1
fi

export PROJECT_DIR
export DEPLOY_MODE

python3 - <<'PY'
import os, re
from pathlib import Path

project_dir = Path(os.environ["PROJECT_DIR"]).resolve()
project_dir_str = str(project_dir)
deploy_mode = os.environ["DEPLOY_MODE"]

# Cron prompt template
TEMPLATE_LOCAL = project_dir / "cronjob_prompt.local.txt"
TEMPLATE_PAGES = project_dir / "cronjob_prompt.pages.txt"
CRON_GENERATED = project_dir / "cronjob_prompt.generated.txt"
DEPLOY_MODE_FILE = project_dir / ".deploy_mode"

if deploy_mode == "pages":
    cron_template = TEMPLATE_PAGES
else:
    cron_template = TEMPLATE_LOCAL

if not cron_template.exists():
    print(f"[WARN] Template not found: {cron_template}, skipping cron prompt generation")
else:
    cron_text = cron_template.read_text(encoding="utf-8")
    # Remove leading 【重要】 block if present
    cron_text = re.sub(
        r"^【重要】.*(?:\r?\n)?",
        "",
        cron_text,
        count=1,
        flags=re.MULTILINE,
    )
    cron_text = cron_text.replace("/path/to/paper-finder", project_dir_str)
    CRON_GENERATED.write_text(cron_text, encoding="utf-8")

DEPLOY_MODE_FILE.write_text(deploy_mode + "\n", encoding="utf-8")

print(f"Patched repository for PROJECT_DIR={project_dir_str}")
print(f"Updated files:")
print(f"- .deploy_mode ({deploy_mode})")
if cron_template.exists():
    print(f"- {cron_template.name}")
    print(f"- cronjob_prompt.generated.txt")
print("")
print("Next step inside Hermes chat:")
print("1. Read the full current contents of cronjob_prompt.generated.txt")
print("2. Send a Hermes slash command: /cron add <prompt>")
print("3. Do not try to run /cron add in bash or a system shell")
PY
