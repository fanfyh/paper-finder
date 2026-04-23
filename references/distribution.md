# Distribution Reference

## Goal

Produce a minimal distributable package from this repository.

## Include

Keep these in the distributable:

- `SKILL.md`
- `config.example.json`
- `references/`
- `profiles/research-interest.example.json`
- `reports/schema/`
- `src/`
- `pyproject.toml`
- `uv.lock`

Add generated files at packaging:
- `install.sh` at package root

## Exclude

Do NOT include:

- `README.md`, `README.zh-CN.md`
- `CODEMAP.md`, `NEXT_PLAN.md`
- `temp/`, `.state/`
- `profiles/research-interest.json` (user's personal config)
- `reports/generated/` (runtime output)

## Current Scope

The packaged skill includes:

- Paper search via OpenAlex
- Profile-based digest
- Zotero semantic search (optional)
- Zotero MCP read/write support
- Email/Telegram delivery (optional)

## Packaging Command

```bash
uv run python scripts/distribution/build_skill_package.py
```

Creates:
- `dist/paper-finder-v<version>/`
- `dist/paper-finder-v<version>.zip`
- `dist/paper-finder-v<version>.tar.gz`

## Installation

The package includes `install.sh`, which:
- Copies runtime files to target directory
- Creates `config.json` from example if missing
- Rewrites runtime paths to actual install target
- Creates `research-interest.json` from example if missing
- Runs `uv sync` when available

After installation:

```bash
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --action search --query "test" --source nber --top 10
```
