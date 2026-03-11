---
name: research-assist
description: A lightweight arXiv literature digest skill for OpenClaw, with Zotero-driven interest profiling, 3-dimensional candidate ranking, and abstract-first review.
---

# Research Assist Skill

A lightweight arXiv literature digest skill for OpenClaw.

## CLI Usage

```bash
# Full digest: profile check → arXiv retrieval → rank → markdown output
research-assist --action digest --config path/to/config.json

# Ad-hoc arXiv search
research-assist --action search --query "gaussian process" --top 5

# Check profile refresh status
research-assist --action profile-refresh --config path/to/config.json
```

Or via Python module:

```bash
python3 -m codex_research_assist --action digest --config ~/.openclaw/skills/research-assist/config.json
```

Default config path: `~/.openclaw/skills/research-assist/config.json`

## Config Format

```json
{
  "profile_path": "~/.openclaw/skills/research-assist/profiles/research-interest.json",
  "output_root": "~/.openclaw/skills/research-assist/reports",
  "retrieval_defaults": {
    "max_results_per_interest": 20,
    "since_days": 7,
    "max_age_days": 7
  }
}
```

## Architecture

```
config.json (OpenClaw skill config)
    ↓
openclaw_runner.py (CLI entry, markdown to stdout)
    ├── profile_refresh_policy  → check if profile needs update
    ├── pipeline.py             → arXiv Atom API retrieval
    ├── ranker.py               → 3-dim scoring (relevance × recency × novelty)
    └── format_*_markdown()     → structured markdown output
```

No LLM calls inside the skill. Retrieval, ranking, and formatting are pure data operations.
Intelligence comes from the calling agent (OpenClaw / Claude Code / Codex CLI).

## Workflow Stages

### 1. `profile_update`

- read the current Zotero evidence base when refresh is required
- maintain `profiles/research-interest.json`
- preserve the compact contract: `method_keywords`, `query_aliases`, `exclude_keywords`
- keep method labels short and retrieval-friendly

### 2. `retrieval`

- query arXiv Atom API per interest
- generate structured candidate JSON with full provenance
- deduplicate across interests

### 3. `review`

- rank candidates with 3-dimensional scoring:
  - **relevance** (0.60): per-phrase keyword overlap against profile interests
  - **recency** (0.25): exponential decay, 7-day full score window
  - **novelty** (0.15): 1.0 if unseen, 0.0 if in history
- output ranked markdown to stdout for agent review
- prefer a smaller sharper set over a noisy dump
- stay `abstract-first`

## Hard Rules

- do not expand concise method labels into long topic sentences
- do not make full text the default review mode
- do not delete Zotero items or collections automatically
- do not treat scheduler wiring as part of the skill

## Key Runtime Files

- OpenClaw runner: `src/codex_research_assist/openclaw_runner.py`
- Ranker: `src/codex_research_assist/ranker.py`
- Pipeline: `src/codex_research_assist/arxiv_profile_pipeline/pipeline.py`
- Live profile: `profiles/research-interest.json`
- Example config: `automation/arxiv-profile-digest.example.toml`

## Reference Documents

- `references/workflow.md` — stage order and controller boundary
- `references/contracts.md` — profile contract and review policy
- `references/distribution.md` — packaging include/exclude rules
- `explain/interests-and-arxiv-matching.md` — plain-language matching explanation

## Packaging Boundary

Include in distributable skill:

- `SKILL.md`, `pyproject.toml`, `uv.lock`
- `src/`
- `references/`
- `profiles/research-interest.example.json`
- `automation/arxiv-profile-digest.example.toml`
- `automation/prompts/`
- `reports/schema/`

Exclude:

- generated reports, temporary state
- local secret config
- scheduler wrappers
- repository planning documents (`NEXT_PLAN.md`, `CODEMAP.md`)
