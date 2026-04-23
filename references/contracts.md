# Contract Reference

## Research Interest Profile

The profile contract in `research-interest.json`:

```json
{
  "interests": [
    {
      "interest_id": "unique-id",
      "label": "Display Name",
      "enabled": true,
      "method_keywords": ["term1", "term2"],
      "query_aliases": ["alias1", "alias2"],
      "exclude_keywords": [],
      "logic": "OR"
    }
  ]
}
```

Rules:
- Keep `method_keywords` short (1-3 terms)
- Keep `query_aliases` focused (0-3 terms)
- Use `logic: "OR"` for broad matching, `"AND"` for narrow
- `exclude_keywords` filters out unwanted results

## Candidate Artifacts

Authoritative artifact:
- candidate `json`

Optional debug artifact:
- candidate `md`

Meaning:
- Downstream processing trusts JSON first
- Markdown is for human inspection only

## Review Policy

Ownership boundary:
- Host agent may only fill `candidate.review`
- Host agent must NOT rewrite `candidate.paper`, provenance, or delivery wrappers
- Email/Telegram templates belong to system-side

Review fields:
- `review.recommendation` — Overall verdict
- `review.why_it_matters` — Why this paper matters
- `review.quick_takeaways` — Key points
- `review.caveats` — Limitations and uncertainties
- `review.zotero_comparison` — Nearest Zotero neighbors (if available)
- `review.generation` — Metadata about how review was generated

Rules:
- `why_it_matters` explains relevance to the research profile
- `quick_takeaways` should be scannable (3-5 bullets)
- `caveats` states uncertainty explicitly
- If Zotero comparison unavailable, say so explicitly
- Prefer 1-2 nearest neighbors

## Delivery Routing

- Use `delivery.primary_channel` to choose outbound channel
- Supported: `email`, `telegram`
- Channels share same data but use different templates
- Do NOT ask agent to write channel-specific wrappers

## Zotero Safety

No automatic:
- Deletes of items or collections
- Collection restructuring
- Metadata modifications (title, authors, etc.)

All writes:
- Default to `dry_run=true` first
- Show preview before applying
- Use non-destructive operations only: add tags, add to collections, append notes

## Zotero MCP Usage

- Use bundled `paper-finder-zotero-mcp` server for live Zotero reads
- During `profile_refresh`: read-only access
- During feedback: default `dry_run=true`
- Encode persistent state with `ra-status:*` tags
