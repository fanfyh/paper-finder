<h1 align="center">research-assist</h1>

<p align="center"><strong>Your Zotero library already knows what you care about.<br/>Let it find next week's papers for you.</strong></p>

<p align="center">
  <img src="assets/readme/hero-overview.svg" alt="research-assist hero" width="100%" />
</p>

<p align="center">
  <a href="README.zh-CN.md"><strong>中文说明</strong></a>
  ·
  <a href="SKILL.md"><strong>Skill Contract</strong></a>
  ·
  <a href="references/workflow.md"><strong>Workflow</strong></a>
  ·
  <a href="references/contracts.md"><strong>Contracts</strong></a>
</p>

<p align="center">
  <code>Zotero-backed</code>
  <code>Semantic search</code>
  <code>AI-enriched digest</code>
  <code>Email delivery</code>
  <code>Feedback loop</code>
</p>

---

> **If you are an agent** (Claude Code, Codex CLI, OpenClaw, or any LLM-backed tool),
> read [`references/setup-routing.md`](references/setup-routing.md) now.
> It will walk you through an interactive setup conversation:
> choose what the user needs, ask only the relevant questions, write `config.json`, and summarize what was enabled.
> **Do not embed the full setup questionnaire here** — route there, complete setup, then return to the user's actual task.
> Once config is valid, never reopen setup during normal runs.

---

## The six-stage chain

<p align="center">
  <img src="assets/readme/six-stage-chain.png" alt="Six-stage chain" width="100%" />
</p>

| Stage | What happens | Output |
|---|---|---|
| **`profile_update`** | Read Zotero evidence (collections, tags, representative papers), maintain a compact research profile | `research-interest.json` |
| **`retrieval`** | Query arXiv Atom API per interest, deduplicate across interests, write candidate artifacts | Candidate JSON + batch manifest |
| **`zotero_evidence`** | Resolve exact matches and semantic neighbors from the local Zotero index for each candidate | Scored candidates with Zotero anchors |
| **`agent_patch`** | Host agent fills `recommendation`, `why_it_matters`, `caveats`, `zotero_comparison`, and final keep/drop | Review patches merged into candidates |
| **`render`** | Generate HTML digest, email body, or Telegram message from the selected subset | `.html` + delivery metadata |
| **`feedback_sync`** | Push non-destructive feedback back into Zotero: add tags, collection membership, append notes | Zotero library updated (dry_run default) |

## What it does — in 30 seconds

1. **Reads your Zotero library** — collections, tags, representative papers — and builds a compact research profile
2. **Searches arXiv against that profile** — not keywords you typed, but evidence from papers you already collected
3. **Ranks candidates** with a two-signal scorer: research-map fit + Zotero semantic affinity
4. **Lets the host agent enrich the top picks** — recommendation, why it matters, nearest Zotero anchors, caveats
5. **Delivers a clean digest** — HTML, email, or Telegram — with only the sharpest papers visible
6. **Feeds the signal back into Zotero** — tags, collections, notes — so the next run starts from a better library

<p align="center">
  <img src="assets/readme/profile-map-card.svg" alt="Profile card" width="100%" />
</p>

<p align="center"><em>A profile reads like a map: compact branches, retrieval-friendly labels, evidence from the library itself.</em></p>

<p align="center">
  <img src="assets/readme/digest-cards.svg" alt="Digest cards" width="100%" />
</p>

<p align="center"><em>A digest scans fast: visible scores, nearest anchors, and AI-written recommendations that justify attention.</em></p>

<p align="center">
  <img src="assets/readme/feedback-loop.svg" alt="Feedback loop" width="100%" />
</p>

<p align="center"><em>The loop closes in Zotero — a useful digest also improves the library it came from.</em></p>

## Why this is different

| Traditional tools | research-assist |
|---|---|
| Start from a keyword list | Start from your actual library |
| Dump everything that matches | Rank, filter, keep only the sharpest |
| AI is bolted on after the fact | AI enrichment is part of the pipeline |
| Results sit in a silo | Feedback flows back into Zotero |

## Quick start

### 1. Install

```bash
git clone <this-repo> && cd research-assist
uv sync
```

That's it. One command installs all dependencies.

### 2. Set up config

```bash
# Create the skill directory and copy the example config
mkdir -p ~/.openclaw/skills/research-assist/profiles
mkdir -p ~/.openclaw/skills/research-assist/reports
cp config.example.json ~/.openclaw/skills/research-assist/config.json
```

Then edit `~/.openclaw/skills/research-assist/config.json` for your setup.

> **If you are an agent**, do not ask the user to fill out a long config form.
> Instead, follow [`references/setup-routing.md`](references/setup-routing.md) — it tells you exactly which questions to ask based on what the user wants to do.

### 3. Run

```bash
# Full digest: profile check → arXiv retrieval → rank → HTML output
uv run research-assist --action digest --config ~/.openclaw/skills/research-assist/config.json

# Ad-hoc search
uv run research-assist --action search --query "llm multi-agent planning" --top 5

# Check if profile needs refresh
uv run research-assist --action profile-refresh --config ~/.openclaw/skills/research-assist/config.json

# Re-render digest after agent patches are merged
uv run research-assist --action render-digest \
  --config ~/.openclaw/skills/research-assist/config.json \
  --digest-json path/to/digest.json \
  --format delivery

# Start the bundled Zotero MCP server
uv run research-assist-zotero-mcp
```

## Pipeline stages

```
Zotero library
    ↓
1. profile_update    → Read Zotero evidence, build a compact research map
    ↓
2. retrieval         → Query arXiv per interest, deduplicate, write candidate JSON
    ↓
3. rank              → Two-signal scoring: map_match (0.30) + zotero_semantic (0.70)
    ↓
4. agent_patch       → Host agent fills: recommendation, why_it_matters, caveats, zotero_comparison
    ↓
5. render            → HTML / email / Telegram from the selected subset
    ↓
6. feedback_sync     → Push tags, collections, notes back into Zotero (dry_run by default)
```

## Key design choices

- **No LLM calls inside the pipeline.** Retrieval, ranking, and formatting are pure data operations. Intelligence comes from the calling agent.
- **Ownership boundary is strict.** The host agent fills only `candidate.review`. It cannot rewrite paper metadata, scores, or delivery wrappers.
- **Digest stays small.** The system can search wide, but the visible digest targets 5 or fewer papers. Sharper shortlist > bigger dump.
- **Feedback is non-destructive.** Zotero writeback defaults to `dry_run=true`. No automatic deletes, no speculative taxonomy rewrites.

## Feedback sync — closing the loop

The final stage pushes what you learned back into Zotero so the next run starts from a better library.

**What feedback can do:**
- Add `ra-status:*` tags (`ra-status:read_first`, `ra-status:archive`, etc.)
- Add or change collection membership
- Append structured notes with decision rationale
- Create new collections for organization

**What feedback will never do:**
- Delete items, collections, or attachments
- Modify paper metadata (title, authors, DOI)
- Apply changes without showing a dry-run plan first

**How it works:**
1. After digest review, the host agent builds a feedback payload per `reports/schema/zotero-feedback.schema.json`
2. Calls `zotero_apply_feedback` with `dry_run=true` to preview changes
3. Shows the plan to the user for confirmation
4. Only then applies with `dry_run=false`

Supported decisions: `read_first`, `skim`, `watch`, `skip_for_now`, `archive`, `watchlist`, `ignore`, `unset`

Items are matched by `item_key`, `doi`, or `title_contains`. Previous `ra-status:*` tags are replaced when a new decision is applied.

## Optional: Zotero semantic search

If you want semantic neighbors (not just exact matches), configure the local search index:

```bash
uv run python - <<'PY'
from codex_research_assist.zotero_mcp.semantic_search import create_semantic_search
search = create_semantic_search()
print(search.update_database(force_rebuild=False))
PY
```

Fill these keys in `config.json`:
- `semantic_search.zotero_db_path` — path to your local `zotero.sqlite`
- `semantic_search.local_group_id` or `semantic_search.local_library_id`

## Architecture

```
config.json
    ↓
openclaw_runner.py          ← CLI entry point, markdown/HTML to stdout
    ├── profile_refresh_policy  → Should the profile be updated?
    ├── pipeline.py             → arXiv Atom API retrieval
    ├── ranker.py               → Two-signal scoring
    ├── review_digest.py        → System-generated review fallback
    ├── review_patch.py         → Agent review patch merge
    ├── html_fmt.py             → Beautiful warm-tone HTML digest
    ├── email_sender.py         → SMTP delivery
    └── telegram_fmt/sender.py  → Telegram delivery
```

## For agents: how to use this skill

> **If you are an agent** reading this for the first time:
>
> 1. Read [`references/setup-routing.md`](references/setup-routing.md) to configure the skill interactively
> 2. Read [`SKILL.md`](SKILL.md) for the full skill contract — CLI usage, workflow stages, hard rules
> 3. Read [`references/workflow.md`](references/workflow.md) for stage order and controller boundaries
> 4. Read [`references/contracts.md`](references/contracts.md) for profile and review ownership rules
>
> **Important behavioral rules:**
> - Setup is a **one-time** operation. Once `config.json` is valid, do not reopen setup questions during normal runs.
> - During digest runs, use the existing config. Do not re-discuss installation options.
> - If config is missing or broken, route back to `setup-routing.md` — do not guess values.

## Reference documents

- [`SKILL.md`](SKILL.md) — Skill contract for OpenClaw / agent integration
- [`references/workflow.md`](references/workflow.md) — Stage order and controller boundary
- [`references/contracts.md`](references/contracts.md) — Profile and review ownership rules
- [`references/setup-routing.md`](references/setup-routing.md) — Interactive agent setup guide
- [`references/review-generation.md`](references/review-generation.md) — Agent-filled review behavior
- [`references/profile-map-generation.md`](references/profile-map-generation.md) — How the research map is built from Zotero evidence

## Demo data in the visuals

The README visuals use a fictional public-topic profile (Agent memory, Multi-agent planning, World models, RL systems, Tool use, Simulation) with real papers as neutral examples.
