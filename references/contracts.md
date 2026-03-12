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
