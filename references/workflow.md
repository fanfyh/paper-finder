# Workflow Reference

## Operating Model

The active operating model is:

- `one controller-backed skill session`

The repository no longer depends on role-split prompt surfaces as its primary control surface.

## Stage Order

### 1. `profile_update`

- decide whether refresh is needed from config and live profile age
- when refresh runs, inspect Zotero through `research-assist-zotero-mcp`
- if refresh runs, write normalized profile JSON to:
  - `profiles/research-interest.json`
  - one timestamped profile report under `reports/generated/`
- this stage should be orchestrated by the OpenClaw controller or host agent, not by a repo-local `codex exec` script

### 2. `retrieval`

- use `src/codex_research_assist/arxiv_profile_pipeline/pipeline.py` through the packaged CLI / runner
- generate:
  - one batch manifest JSON
  - per-paper candidate JSON files
  - optional candidate Markdown files only when debug mode is enabled

### 3. `review`

- read the live profile plus retrieval manifest and candidate JSON
- produce one structured literature review JSON
- preserve provenance and ranking rationale
- keep Zotero writeback outside this stage's output

### 4. `agent_fill`

- use as the default host-side digest enrichment step
- enrich the top-ranked candidate JSON files with assistant-written review text
- keep fallback to `system` review text when agent fill is unavailable and fallback is enabled
- write review patches that conform to `reports/schema/review-patch.schema.json`
- keep Zotero access read-only in this stage
- this stage should be orchestrated by the OpenClaw controller or host agent, not by a repo-local `codex exec` script

### 5. `render`

- re-render the final digest from the patched candidate JSON artifacts
- use `research-assist --action render-digest --config <config.json> --digest-json <digest.json>`
- this stage should happen after agent patches are merged

### Optional later extension: `zotero_feedback`

- resolve target Zotero items through MCP search/read tools
- generate one feedback JSON report conforming to `reports/schema/zotero-feedback.schema.json`
- apply writeback in `dry_run=true` first, then only opt into explicit non-destructive writes

### 6. `delivery`

- branch at the end with `delivery.primary_channel`
- default primary route is `email`
- `telegram` can be alternate primary or runtime fallback
- channel wrappers are system-owned, not agent-owned
- keep HTML artifacts even when direct delivery is enabled

## Naming Guidance

The runtime surface uses functional directories:

- `scripts/core/`
- `scripts/profile/`
- `src/codex_research_assist/zotero_mcp/`

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
