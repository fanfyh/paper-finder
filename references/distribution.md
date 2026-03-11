# Distribution Reference

## Goal

Produce one minimal distributable skill package from this repository.

The distributed package is intentionally smaller than the source repository.

## Include

Keep these items in the distributable skill:

- `SKILL.md`
- `references/`
- `assets/templates/`
- `automation/prompts/`
- `automation/workflows/research-interest-digest/run-spec.template.txt`
- `automation/arxiv-profile-digest.example.toml`
- `profiles/research-interest.example.json`
- `reports/schema/`
- `scripts/core/run_codex_task.sh`
- `scripts/workflow/run_digest_workflow.sh`
- `scripts/retrieval/run_arxiv_pipeline.sh`
- `scripts/profile/refresh_profile.sh`
- `scripts/review/review_candidates.sh`
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

Temporarily out of packaged baseline:

- scheduler wiring
- Gmail intake setup
- SMTP delivery setup

These can return later as optional extensions, but they are not part of the current distributable baseline.
