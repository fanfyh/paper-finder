# Distribution Reference

## Goal

Produce one minimal distributable skill package from this repository.

The distributed package is intentionally smaller than the source repository.

## Include

Keep these items in the distributable skill:

- `SKILL.md`
- `references/`
- `automation/prompts/`
- `automation/arxiv-profile-digest.example.toml`
- `profiles/research-interest.example.json`
- `reports/schema/`
- `src/`
- `pyproject.toml`
- `uv.lock`

## Exclude

Do not include these items in the minimal packaged skill:

- `README.md`
- `CODEMAP.md`
- `NEXT_PLAN.md`
- `temp/`
- `.state/`
- `automation/*.local.toml`
- `profiles/research-interest.json`
- `reports/generated/`

## Current Scope Decision

The minimal packaged skill currently focuses on:

- `profile_update`
- `retrieval`
- `review`
- `render`
- `delivery`
- bundled Zotero MCP read/write support
- host-side orchestration by OpenClaw rather than repo-local `codex exec` wrappers
- machine-readable digest handoff artifacts for host-side orchestration

Temporarily out of packaged baseline:

- scheduler wiring

These can return later as optional extensions, but they are not part of the current distributable baseline.
