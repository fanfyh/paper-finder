# Workflow Reference

## Operating Model

The active operating model is:

- `one controller-backed skill session`

The repository no longer depends on role-split prompt surfaces as its primary control surface.

## Stage Order

### 1. `profile_update`

- decide whether refresh is needed from config and live profile age
- if refresh runs, write normalized profile JSON to:
  - `profiles/research-interest.json`
  - one timestamped profile report under `reports/generated/`

### 2. `retrieval`

- use `scripts/retrieval/run_arxiv_pipeline.sh`
- generate:
  - one batch manifest JSON
  - per-paper candidate JSON files
  - optional candidate Markdown files only when debug mode is enabled

### 3. `review`

- read the live profile plus retrieval manifest and candidate JSON
- produce one structured literature review JSON
- preserve provenance and ranking rationale

### Optional later extension: `delivery`

- keep SMTP delivery outside the minimal packaged baseline
- reintroduce it only when local config and delivery requirements are explicitly needed

## Naming Guidance

The runtime surface uses functional directories:

- `scripts/profile/`
- `scripts/retrieval/`
- `scripts/review/`
- `scripts/workflow/`

## Controller Boundary

The controller should:

- interpret the stage plan
- execute the enabled stages
- track artifact paths
- emit one final controller summary JSON

The controller should not:

- grow a new shell-chain orchestrator
- reintroduce split role-specific prompt layers
- depend on memory maintenance for one run
- depend on scheduler wrappers in the minimal packaged baseline
