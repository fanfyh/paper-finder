# Zotero Feedback Contract

Non-destructive Zotero feedback system for `paper-finder`.

## Goals

- Safe, incremental way to record user feedback into Zotero
- All operations non-destructive by default
- Persist decisions: `read_first`, `skim`, `watch`, `skip_for_now`, `archive`, `watchlist`, `ignore`, `unset`

## Safety Rules (Hard)

- Do NOT delete Zotero items
- Do NOT delete Zotero collections
- Do NOT mass-move items unless explicitly requested
- Do NOT rewrite user's taxonomy speculatively
- Default to `dry_run=true` before applying changes

## Feedback Payload Schema

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-03-11T00:00:00+00:00",
  "source": "paper-finder",
  "decisions": [
    {
      "match": {
        "item_key": "ABCDE123",
        "doi": "10.1000/xyz",
        "title_contains": "economics"
      },
      "decision": "archive",
      "rationale": "High relevance to current profile.",
      "add_tags": ["survey", "key-paper"],
      "remove_tags": ["to-read"],
      "add_collections": ["Archive"],
      "remove_collections": [],
      "note_append": "Keep for survey section."
    }
  ]
}
```

### Matching

Each decision must match using at least one of:
- `item_key` (strongest, stable)
- `doi` (strong if present)
- `title_contains` (weak fallback)

### Supported Decisions

- `read_first` — High priority
- `skim` — Worth scanning
- `watch` — Track topic area
- `skip_for_now` — Not relevant now
- `archive` — Reviewed and filed
- `watchlist` — Standing watchlist
- `ignore` — Suppress in future
- `unset` — No action

## How Feedback Is Applied

The MCP tool `zotero_apply_feedback` performs:
- Adds tags in `add_tags`
- Removes tags in `remove_tags`
- Adds status tag: `ra-status:<decision>` (except `unset`)
- Ensures system tag `paper-finder` exists
- Adds/removes collections
- Appends child note with feedback event

Special cases:
- `unset`: no-op for writeback
- `dry_run=true`: missing collections reported, not created
- `dry_run=false`: missing collections may be created

All operations are idempotent and safe to re-run.
