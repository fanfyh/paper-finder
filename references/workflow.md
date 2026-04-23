# Workflow Reference

## Operating Model

- CLI-based tool with optional agent integration
- Core functions work standalone
- Zotero integration is optional

## Stage Order

### 1. `search` — Paper Retrieval

- Query OpenAlex API by keyword and source
- Sources: `nber`, specific journals, `all`, or `openalex` (full database)
- Output: JSON + Markdown candidate files

### 2. `digest-all` — Profile-based Digest (optional)

- Requires `research-interest.json` profile
- Retrieves papers from configured sources
- Ranks by profile match + semantic similarity (if enabled)
- Output: Ranked digest with enriched reviews

### 3. `sync-index` — Zotero Semantic Index (optional)

- Syncs Zotero library to semantic search index
- Uses embedding model for similarity matching
- Required for semantic ranking

### 4. `profile-refresh` — Update Research Profile (optional)

- Reads Zotero evidence (collections, tags, papers)
- Updates `research-interest.json`
- Orchestrate by host agent or run manually

### 5. `render` — Digest Output

- Generates HTML digest from ranked candidates
- Email or Telegram delivery (if configured)
- Local HTML output always available

### Optional: `feedback_sync` — Zotero Writeback

- Non-destructive feedback to Zotero
- Adds tags, collections, notes
- Default `dry_run=true`

## Data Flow

```
User Input (keywords OR profile)
         │
         ▼
OpenAlex Retrieval
         │
         ▼
  ┌──────┴──────┐
  │             │
Keyword    Semantic
Match      Similarity
  │             │
  └──────┬──────┘
         ▼
    Ranking
         │
         ▼
    Output
   (HTML/Email)
```

## CLI Commands

```bash
# Search
paper-finder --action search --query "keyword" --source nber --top 20

# Digest
paper-finder --action digest-all

# Sync index
paper-finder --action sync-index

# Refresh profile
paper-finder --action profile-refresh
```

## Component Locations

- CLI runner: `src/codex_research_assist/openclaw_runner.py`
- OpenAlex client: `src/codex_research_assist/openalex_pipeline/`
- NBER pipeline: `src/codex_research_assist/nber_pipeline/`
- Zotero MCP: `src/codex_research_assist/zotero_mcp/`
- Ranker: `src/codex_research_assist/ranker.py`
