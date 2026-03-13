# Zotero Feedback Contract

This document defines the non-destructive Zotero feedback system used by the `research-assist` skill.

## Goals

- provide a safe, incremental way to record user feedback into Zotero
- keep all operations non-destructive by default
- allow an agent to persist `read_first`, `skim`, `watch`, `skip_for_now`, `archive`, `watchlist`, `ignore`, and `unset` decisions
- support small corrections to tags and collections without taxonomy rewrites

## Safety Rules (Hard)

- do not delete Zotero items
- do not delete Zotero collections
- do not mass-move items across collections unless explicitly requested
- do not rewrite user's top-level collection taxonomy speculatively
- default to `dry_run=true` before applying any change

## Feedback Payload Schema

The feedback payload is a JSON object with this shape:

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-03-11T00:00:00+00:00",
  "source": "research-assist",
  "decisions": [
    {
      "match": {
        "item_key": "ABCDE123",
        "doi": "10.1000/xyz",
        "title_contains": "physics-informed"
      },
      "decision": "archive",
      "rationale": "High relevance to current profile; good survey baseline.",
      "add_tags": ["survey", "pinn"],
      "remove_tags": ["to-read"],
      "add_collections": ["Archive"],
      "remove_collections": [],
      "note_append": "Keep for survey section 2.1."
    }
  ]
}
```

### Matching semantics

Each decision must match a Zotero item using at least one of:

- `item_key` (strongest, stable)
- `doi` (strong if present)
- `title_contains` (weak fallback; use carefully)

Supported decisions:

- `read_first`
- `skim`
- `watch`
- `skip_for_now`
- `archive`
- `watchlist`
- `ignore`
- `unset`

## How Feedback Is Applied

The MCP tool `zotero_apply_feedback` performs the following actions per matched item:

- adds tags in `add_tags`
- removes tags in `remove_tags`
- adds one status tag: `ra-status:<decision>` (except `unset`)
- ensures the system tag `research-assist` exists
- adds/removes collections as requested
- appends a Zotero child note recording the feedback event

Special cases:

- `unset` is a no-op for writeback: it is reported in the plan but does not change tags, collections, or notes
- with `dry_run=true`, missing collections are reported in the plan and are not created yet
- with `dry_run=false`, missing collections requested in `add_collections` may be created as part of the apply step

All operations are intended to be idempotent and safe to re-run.
