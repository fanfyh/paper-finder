---
name: paper-finder
description: OpenAlex-based literature discovery tool for economics. Search NBER working papers and top journals, with optional Zotero-driven interest profiling and semantic ranking.
---

# Paper-Finder Skill

An OpenAlex-based literature discovery tool for economics. Search NBER working papers and top journals, with optional Zotero-driven interest profiling and semantic ranking.

## CLI Usage

```bash
# Global search (default, all sources)
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "fiscal competition" --top 20

# Search NBER only
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "fiscal competition" --source nber --top 20

# Search specific journal
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "housing" --source JPubE --top 20

# Subscribe to digest (based on research profile)
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action digest-all

# Sync Zotero to semantic index
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action sync-index

# Zotero MCP server (for semantic search + feedback writeback)
uv run --project ~/.claude/tools/paper-finder paper-finder-zotero-mcp
```

Default config path: `~/.claude/tools/paper-finder/config.json`

## Install-Time Behavior

Installation and reconfiguration are one-time operations.

Hard rules for the host agent:

- use `references/setup-routing.md` only when the user is installing, reconfiguring, or when required config is missing
- once `config.json` is valid, normal digest/search runs must not reopen setup questions
- when setup selects optional backends or delivery routes, execute the required install/setup commands
- before leaving setup, run a minimal verification for the selected backend

## Config Format

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
  }
}
```

## Architecture

```
config.json
    ↓
openclaw_runner.py (CLI entry)
    ├── openalex_pipeline/  → OpenAlex API retrieval
    ├── nber_pipeline/      → NBER working papers
    ├── ranker.py           → scoring (keywords + semantic)
    └── html_fmt.py         → HTML digest output
```

No LLM calls inside the packaged Python pipeline. Retrieval, ranking, and formatting are pure data operations.

## Core Functions

### search — Paper Retrieval

Query OpenAlex API for papers by keyword.

**Default behavior**: Global search across all sources (no journal restriction).

**Optional sources** (only when explicitly specified):
- `nber` — NBER working papers only
- Journal aliases (see below) — Specific journal only

### Available Journal Sources

Based on 中央财经大学期刊目录（2025版） AAA & AA 类：

**AAA - Economics:**
| Alias | Journal |
|-------|---------|
| AER | American Economic Review |
| JPE | Journal of Political Economy |
| QJE | Quarterly Journal of Economics |
| RES | Review of Economic Studies |
| ECONOMETRICA | Econometrica |

**AAA - Political Science:**
| Alias | Journal |
|-------|---------|
| APSR | American Political Science Review |
| AJPS | American Journal of Political Science |
| WP | World Politics |

**AAA - Sociology:**
| Alias | Journal |
|-------|---------|
| AJS | American Journal of Sociology |
| ASR | American Sociological Review |
| SF | Social Forces |

**AA - Economics (selected):**
| Alias | Journal |
|-------|---------|
| JPubE | Journal of Public Economics |
| JUE | Journal of Urban Economics |
| REStat | Review of Economics and Statistics |
| JME | Journal of Monetary Economics |
| EJ | Economic Journal |
| JET | Journal of Economic Theory |
| GEB | Games and Economic Behavior |
| JFE | Journal of Financial Economics |
| RJE | Rand Journal of Economics |
| TE | Theoretical Economics |
| JEEA | Journal of the European Economic Association |
| JDE | Journal of Development Economics |
| EER | European Economic Review |
| JEBO | Journal of Economic Behavior & Organization |
| RSUE | Regional Science and Urban Economics |
| JLE | Journal of Labor Economics |
| OEP | Oxford Economic Papers |
| NTJ | National Tax Journal |

**AA - Political Science (selected):**
| Alias | Journal |
|-------|---------|
| BJPS | British Journal of Political Science |
| CPS | Comparative Political Studies |
| EJPR | European Journal of Political Research |
| PA | Political Analysis |
| GOVERNANCE | Governance |

**AA - Sociology:**
| Alias | Journal |
|-------|---------|
| DEMOG | Demography |
| SM | Sociological Methodology |
| SSR | Social Science Research |
| SOCNET | Social Networks |

**AA - Public Administration:**
| Alias | Journal |
|-------|---------|
| JPAM | Journal of Policy Analysis and Management |
| JPART | Journal of Public Administration Research and Theory |
| JEPP | Journal of European Public Policy |
| PAR | Public Administration Review |
| PMR | Public Management Review |

Full alias list available in `openclaw_runner.py:JOURNAL_ALIAS`.

### digest-all — Subscription Digest

Retrieve papers from configured sources based on research profile, rank by relevance, and deliver digest.

### sync-index — Zotero Semantic Index

Build or update the semantic search index from Zotero library.

### profile-refresh — Update Research Profile

Refresh research interest profile based on Zotero evidence.

## Zotero Integration (Optional)

### Semantic Search

When enabled, uses Zotero library as semantic reference for ranking:
- Extracts embeddings from Zotero items
- Finds semantically similar papers for each candidate
- Boosts ranking for papers close to your library

### Feedback Writeback

Non-destructive feedback system:

Allowed operations:
- Add tags (including decision tags like `ra-status:read_first`)
- Add or change collection membership
- Append notes to items
- Create new collections

Prohibited operations:
- Delete Zotero items or collections
- Modify item metadata (title, authors, abstract, DOI)
- Apply changes without dry-run preview first

## Hard Rules

- Search function works standalone, no Zotero required
- Prefer `dry_run=true` for any Zotero writeback
- Do not expand concise method labels into long topic sentences
- Do not make full text the default review mode
- Do not delete Zotero items or collections automatically

## Key Runtime Files

- CLI runner: `src/codex_research_assist/openclaw_runner.py`
- OpenAlex client: `src/codex_research_assist/openalex_pipeline/`
- NBER pipeline: `src/codex_research_assist/nber_pipeline/`
- Ranker: `src/codex_research_assist/ranker.py`
- Example config: `config.example.json`
- Example profile: `profiles/research-interest.example.json`

## Reference Documents

- `references/workflow.md` — workflow stages
- `references/contracts.md` — data contracts
- `references/setup-routing.md` — install-time setup guide
- `references/zotero-mcp.md` — Zotero MCP server
