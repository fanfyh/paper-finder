# research-assist

> Build a research profile from Zotero, search arXiv against it, let AI keep the sharpest papers, and feed the signal back into Zotero.

<p align="center">
  <img src="assets/readme/hero-overview.svg" alt="research-assist hero" width="100%" />
</p>

<p align="center">
  <a href="README.zh-CN.md"><strong>中文说明</strong></a>
  ·
  <a href="SKILL.md"><strong>SKILL</strong></a>
  ·
  <a href="references/workflow.md"><strong>Workflow</strong></a>
  ·
  <a href="references/contracts.md"><strong>Contracts</strong></a>
  ·
  <a href="references/setup-routing.md"><strong>Setup routing</strong></a>
</p>

<p align="center">
  <code>Zotero-backed</code>
  <code>OpenClaw-ready</code>
  <code>Agent-patched digest</code>
  <code>Email-first delivery</code>
  <code>Feedback loop</code>
</p>

## Why this feels different

- **It starts from a library, not a keyword list.** Collection structure, representative papers, and semantic neighbors are blended into a profile that behaves like a retrievable research map.
- **It optimizes for a sharper shortlist, not a bigger dump.** The pipeline can surface more candidates, but the visible digest is meant to stay small, legible, and decision-ready.
- **AI recommendation is part of the workflow, not a detached afterthought.** The host agent fills `why_it_matters`, nearest Zotero anchors, quick takeaways, caveats, and the final keep/drop decision.
- **Feedback goes back into the library.** Tags, collection membership, and non-destructive cleanup can be pushed back into Zotero so the next run starts from a better map.

## What it looks like

<p align="center">
  <img src="assets/readme/profile-map-card.svg" alt="Profile card demo" width="100%" />
</p>

A good profile should read like a map: compact branches, retrieval-friendly labels, and evidence that comes from the library itself.

<p align="center">
  <img src="assets/readme/digest-cards.svg" alt="Digest card demo" width="100%" />
</p>

A good digest should scan fast: visible scores, nearest anchors, and AI-written recommendation text that justifies attention.

<p align="center">
  <img src="assets/readme/feedback-loop.svg" alt="Feedback loop demo" width="100%" />
</p>

The loop matters because a useful digest should also improve the library it came from.

## Four things to notice

### 1. Profile map, not profile dump

`research-assist` treats Zotero like a palette:

- collections provide the sketch
- representative papers provide the strong pigment
- semantic neighbors soften hard folder edges and expose hidden continuity

The result is a profile that can drive retrieval, ranking, and later recommendation.

### 2. Retrieval can be broad, digest stays selective

The workflow can retrieve more than it finally shows. A practical pattern is:

- retrieve a broader batch
- rank to a compact top 8
- let the host agent keep `<= 5`
- render only the final visible digest

That separation is deliberate. The system can search wide without forcing the reader to scan wide.

### 3. AI recommendation is grounded

The host agent does not rewrite paper metadata or delivery wrappers. It only enriches the paper-level review:

- `recommendation`
- `why_it_matters`
- `quick_takeaways`
- `caveats`
- `zotero_comparison`
- `selected_for_digest`

This keeps the agent focused on judgment while system-owned templates handle HTML, email, Telegram, and routing.

### 4. The loop closes in Zotero

After review, the same run can optionally push non-destructive feedback back into Zotero:

- add tags
- add or move collection membership
- append notes
- stage cleanup suggestions through `dry_run`

That is the difference between a digest generator and a library-improving assistant.

## Demo branches used in the visuals

The README visuals use a fictional public-topic profile so they stay easy to understand and do not reveal any real user direction:

- Agent memory
- Multi-agent planning
- World models
- RL systems
- Tool use
- Simulation

## Demo paper anchors used in the visuals

These are real papers, used only as neutral README examples:

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
- [Voyager: An Open-Ended Embodied Agent with Large Language Models](https://arxiv.org/abs/2305.16291)
- [Mastering Diverse Domains through World Models](https://arxiv.org/abs/2301.04104)
- [Multi-agent Reinforcement Learning: A Comprehensive Survey](https://arxiv.org/abs/2312.10256)
- [A Survey on LLM-based Multi-Agent System: Recent Advances and New Frontiers in Application](https://arxiv.org/abs/2412.17481)

## Quick start

### 1. Install the repo dependencies

```bash
uv sync
```

### 2. Prepare one-time skill config

```bash
mkdir -p ~/.openclaw/skills/research-assist/profiles
mkdir -p ~/.openclaw/skills/research-assist/reports

cp config.example.json ~/.openclaw/skills/research-assist/config.json
cp profiles/research-interest.example.json \
  ~/.openclaw/skills/research-assist/profiles/research-interest.json
```

If you want the host agent to configure the skill interactively, let it follow [`references/setup-routing.md`](references/setup-routing.md) and edit `~/.openclaw/skills/research-assist/config.json` directly.

Important:

- installation and reconfiguration are **one-time** setup tasks
- once `config.json` is valid, normal digest runs should **not** reopen the setup questionnaire
- setup questions should return only when the user explicitly asks to reconfigure, or when required config is missing

### 3. Configure Zotero and semantic search only if you need them

Minimal digest mode does **not** require Zotero credentials.

If you want live Zotero-backed profiling and semantic neighbors, fill the relevant keys in `config.json`:

- `zotero.library_id`
- `zotero.library_type`
- `zotero.api_key`
- `semantic_search.zotero_db_path`
- `semantic_search.local_group_id` or `semantic_search.local_library_id`

To bootstrap the local semantic index:

```bash
uv run python - <<'PY'
from codex_research_assist.zotero_mcp.semantic_search import create_semantic_search

search = create_semantic_search()
print(search.update_database(force_rebuild=False))
PY
```

### 4. Run the pipeline

```bash
# full digest
uv run research-assist --action digest --config ~/.openclaw/skills/research-assist/config.json

# ad-hoc search
uv run research-assist --action search --query "llm multi-agent planning" --top 5

# check profile refresh policy
uv run research-assist --action profile-refresh --config ~/.openclaw/skills/research-assist/config.json

# re-render the final digest after agent patches have been merged
uv run research-assist --action render-digest \
  --config ~/.openclaw/skills/research-assist/config.json \
  --digest-json path/to/digest.json \
  --format delivery

# bundled Zotero MCP
uv run research-assist-zotero-mcp
```

## Stage map

1. `profile_update`
   Read Zotero evidence and maintain a compact research profile.
2. `retrieval`
   Query arXiv, deduplicate, and write ranked candidate artifacts.
3. `zotero_evidence`
   Resolve exact and semantic anchors from Zotero.
4. `agent_patch`
   Let the host agent fill review text and final keep/drop decisions.
5. `render`
   Produce HTML, email, or Telegram outputs from the selected subset.
6. `feedback_sync`
   Push non-destructive cleanup and organization back into Zotero.

## Ownership boundary

- The host agent should fill only `candidate.review`.
- The host agent should not rewrite `candidate.paper`, scores, provenance, or channel wrappers.
- Email subject/body, Telegram wrapper text, stat cards, profile card, and routing are system-owned.
- Email is the default primary delivery route; Telegram is an alternate or fallback route.
- Feedback writeback should default to `dry_run=true`.

## Read next

- [`SKILL.md`](SKILL.md) for the skill contract used by OpenClaw
- [`references/workflow.md`](references/workflow.md) for stage order and controller boundaries
- [`references/contracts.md`](references/contracts.md) for profile and review ownership rules
- [`references/review-generation.md`](references/review-generation.md) for agent-filled review behavior
- [`references/profile-map-generation.md`](references/profile-map-generation.md) for how the research map is painted from Zotero evidence
- [`references/zotero-mcp.md`](references/zotero-mcp.md) for bundled Zotero tools
