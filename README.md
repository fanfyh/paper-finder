<h1 align="center">Paper-Finder</h1>

<p align="center"><strong>OpenAlex-based literature discovery tool for economics.<br/>Search NBER working papers and top journals by your research interests.</strong></p>

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
  <code>OpenAlex Search</code>
  <code>NBER + Top Journals</code>
  <code>Research Profile</code>
  <code>Semantic Ranking</code>
  <code>Email Delivery</code>
</p>

---

## Core Features

| Feature | Description | Dependencies |
|---------|-------------|--------------|
| **Paper Search** | Search by keywords across NBER, 17 journals, or full OpenAlex | None |
| **Subscription Digest** | Regular paper pushes based on your research profile | Profile config |
| **(Optional) Zotero Enhancement** | Use your Zotero library to improve ranking | Zotero + semantic search |

---

## Quick Start

### Basic Search

```bash
export PATH="$HOME/.local/bin:$PATH" && \
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "fiscal competition" --source nber --top 20

# Search specific journal
--action search --query "housing" --source JPE --top 20

# Search full OpenAlex database
--action search --query "urban economics" --source openalex --top 20
```

### Subscription Digest

Configure your research profile first (see Configuration), then:

```bash
--action digest-all
```

### Zotero Enhancement (Optional)

```bash
# Sync Zotero to semantic index
--action sync-index

# Update research profile
--action profile-refresh
```

---

## Use Cases

### Use Case 1: Monthly Subscription

**Goal**: Regularly retrieve new papers from your selected journals/sources (e.g., NBER), filtered by research interests.

**Usage**:
1. Configure your research interests in `research-interest.json`
2. Run `digest-all` command
3. System retrieves papers from the past month, ranks by interest match
4. Results delivered via email or HTML

### Use Case 2: Feedback Learning (Optional)

**Goal**: Rate pushed papers to iteratively improve your research profile.

**Usage**:
1. Mark each paper with a status after digest delivery (`read_first`, `skim`, `archive`, `skip_for_now`, etc.)
2. System writes feedback to Zotero (tags, collections, notes)
3. Future digests adjust ranking based on feedback

### Use Case 3: Semantic Search

**Goal**: Retrieve papers by semantic analysis, not just keyword matching.

**Usage**:
- Requires Zotero semantic search enabled
- System uses your Zotero library as semantic reference
- Returned papers show "nearest Zotero items"

### Use Case 4: Journal Preference Analysis (Planned)

**Goal**: Analyze a journal's topical preferences by reviewing the past year of publications.

**Status**: To be implemented

---

## Data Sources

### NBER Working Papers

Direct retrieval of NBER working papers across all research programs.

### 17 Economics & Politics Journals

| Code | Journal |
|------|---------|
| AER | American Economic Review |
| JPE | Journal of Political Economy |
| QJE | Quarterly Journal of Economics |
| RES | Review of Economic Studies |
| REStat | Review of Economics and Statistics |
| EJ | Economic Journal |
| Econometrica | Econometrica |
| JPubE | Journal of Public Economics |
| JDE | Journal of Development Economics |
| JUE | Journal of Urban Economics |
| AJPS | American Journal of Political Science |
| APSR | American Political Science Review |
| BJPS | British Journal of Political Science |
| PA | Political Analysis |
| WP | World Politics |
| Governance | Governance |
| RP | Research Policy |

### OpenAlex Full Database

Unrestricted search across the entire OpenAlex database.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                            │
│  Keyword search / Research profile / Zotero library (optional)│
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     OpenAlex Retrieval                       │
│  NBER API / Journal filters / Full database search           │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Matching & Ranking                      │
│  Keyword match / Profile score / Zotero semantic similarity   │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Output & Feedback                       │
│  HTML digest / Email delivery / Zotero writeback (optional)   │
└─────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Search-first** — OpenAlex retrieval is core, Zotero is optional enhancement
2. **Streaming pipeline** — Retrieval, ranking, and output are separate stages
3. **Non-destructive feedback** — Zotero writeback defaults to `dry_run=true`
4. **Agent-native** — Integrates with Claude Code and other LLM tools

---

## Configuration

### config.json

Main configuration file at `~/.claude/tools/paper-finder/config.json`.

**Key settings**:

```json
{
  "profile_path": "~/.claude/tools/paper-finder/profiles/research-interest.json",
  "output_root": "/path/to/output",
  "zotero": {
    "library_id": "your_library_id",
    "api_key": "your_api_key"
  },
  "semantic_search": {
    "enabled": true,
    "zotero_db_path": "/path/to/zotero.sqlite"
  },
  "delivery": {
    "primary_channel": "email",
    "email": {
      "send_enabled": true,
      "recipients": ["your@email.com"]
    }
  }
}
```

### research-interest.json

Research profile defining your interests.

**Structure**:

```json
{
  "interests": [
    {
      "interest_id": "public-finance",
      "label": "Public Finance",
      "enabled": true,
      "method_keywords": ["tax", "fiscal", "government spending"],
      "query_aliases": ["taxation", "public finance", "fiscal policy"],
      "exclude_keywords": [],
      "logic": "OR"
    }
  ]
}
```

---

## Command Reference

### search — Paper Retrieval

```bash
--action search --query "keywords" --source <SOURCE> --top N
```

| Parameter | Description |
|-----------|-------------|
| `--query` | Search keywords |
| `--source` | Source: `nber` / `JPE,AER,...` / `all` / `openalex` |
| `--top` | Number of results |

### digest-all — Subscription Digest

```bash
--action digest-all
```

Retrieve and push new papers based on research profile.

### sync-index — Zotero Sync

```bash
--action sync-index
```

Sync Zotero library to semantic search index.

### profile-refresh — Update Profile

```bash
--action profile-refresh
```

Update research profile based on Zotero library.

---

## Development

### Install dependencies

```bash
cd ~/.claude/tools/paper-finder
uv sync
```

### Run tests

```bash
uv run pytest
```

---

## Reference Documents

- [`SKILL.md`](SKILL.md) — Skill contract specification
- [`references/workflow.md`](references/workflow.md) — Workflow details
- [`references/contracts.md`](references/contracts.md) — Data contract definitions
