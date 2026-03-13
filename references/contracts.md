# Contract Reference

## Research Interest Profile

The live profile contract is:

- `method_keywords`
- `query_aliases`
- `exclude_keywords`

Rules:

- prefer short method labels
- keep each interest compact
- keep `method_keywords` usually at 1-2 terms
- keep `query_aliases` usually at 0-2 terms
- retrieval should use at most the first 3 terms
- do not regress to long sentence-style topic phrases

## Candidate Artifacts

Authoritative artifact:

- candidate `json`

Optional debug artifact:

- candidate `md`

Meaning:

- downstream review should trust JSON first
- Markdown is only for human debugging or inspection

## Review Policy

- default to `abstract-first`
- rank by fit to the live profile
- trim weak or off-target items
- prefer concise output over exhaustive output

Ownership boundary:

- the host agent may only fill `candidate.review`
- the host agent must not rewrite `candidate.paper`, candidate provenance, or delivery wrappers
- email / telegram title, body shell, profile card, statistics card, and attachment policy belong to system-side delivery templates
- channel routing belongs to config + runtime, not to agent prose

Digest-facing review fields may include:

- `review.recommendation`
- `review.why_it_matters`
- `review.quick_takeaways`
- `review.caveats`
- `review.zotero_comparison`
- `review.generation`

Rules:

- `why_it_matters` should explain why the paper is worth attention for the active profile now
- `quick_takeaways` should stay short and scannable
- `caveats` should state uncertainty and missing evidence explicitly
- if Zotero comparison was not run, say so rather than inferring library context
- if the review was agent-filled, record that in `review.generation.mode`
- nearest-neighbor recovery belongs inside `review.zotero_comparison`, not in delivery-layer prose
- prefer 1-2 nearest neighbors for rendering; if only one clean anchor exists, keep one

## Delivery Routing

- use `delivery.primary_channel` to choose the primary outbound channel
- currently supported primary channels are `email` and `telegram`
- email and telegram share the same ranked candidate / review data, but they must use different presentation templates
- do not ask the host agent to write channel-specific wrappers such as email subjects, email profile cards, or telegram intro text
- fallback from email to telegram is runtime policy, not agent policy

## Zotero Safety

- no automatic delete
- no automatic collection deletion
- no speculative top-level taxonomy rewrites
- prefer explicit rationale for any future write action

## Zotero MCP Usage

- use the bundled `research-assist-zotero-mcp` server for live Zotero reads
- during `profile_update`, keep Zotero access read-only
- during feedback sync, default to `dry_run=true`
- only use non-destructive writes: add tags, add collection membership, append notes
- encode persistent item state with `ra-status:*` tags rather than destructive cleanup
