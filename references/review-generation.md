# Review Generation

This document defines how digest-facing review text is generated.

The default OpenClaw path is:

1. retrieval generates candidate JSON artifacts
2. the host agent enriches the top-ranked candidates with review patches
3. the host re-renders the digest from the patched candidate artifacts

The rendering layer should consume the same `candidate.review` structure whether the content came from system fallback or agent patches.

## Shared target fields

The review block in each candidate JSON should converge to:

- `review_status`
- `reviewer_summary`
- `zotero_comparison`
- `recommendation`
- `why_it_matters`
- `selected_for_digest`
- `quick_takeaways`
- `caveats`
- `generation`

## System fallback

Use when:

- agent review has not run yet
- the host still wants a minimally readable digest artifact
- agent review failed and fallback is allowed

Behavior:

- generate review text from profile labels, ranking signals, and abstract-first evidence
- do not claim live Zotero comparison unless it was actually run
- mark the generation mode as `system_profile_only`

## Agent fill

Use when:

- the user wants assistant-perspective recommendations
- profile context alone is not enough
- Zotero evidence should inform the final note

Behavior:

- the host agent reads the current candidate JSON
- the host agent reads the live profile
- the agent may query Zotero through the bundled MCP, read-only
- the agent writes a review patch that conforms to `reports/schema/review-patch.schema.json`
- the patch is merged into `candidate.review`
- the host re-renders the digest after patches are applied
- if candidate-level nearest-neighbor evidence is partial or missing, the same agent-fill stage should recover or restate it inside `review.zotero_comparison`

Non-goals for agent fill:

- do not generate email subjects
- do not generate email body wrappers
- do not generate telegram wrappers
- do not decide delivery channel routing
- do not rewrite profile-card copy that belongs to the runtime mail template

## Agent-fill rules

- do not rewrite candidate provenance
- do not write to Zotero in this stage
- if Zotero evidence is absent or weak, say so explicitly in `caveats`
- `zotero_comparison` should always be explicit rather than left blank
- if `_scores.semantic_neighbors` is missing or thin, the agent should use available Zotero evidence or a read-only lookup to fill `zotero_comparison.related_items`
- the preferred shape is 1-2 nearest neighbors, kept compact enough for rendering
- `why_it_matters` must answer why this paper deserves attention now for the active profile
- `why_it_matters` should read like a recommendation from the assistant, not like a Zotero evidence log
- `reviewer_summary` should be a short assistant-written synthesis, not a raw abstract dump
- `quick_takeaways` should stay short, usually 2-4 items
- `quick_takeaways` should emphasize method axis, problem setting, and comparison value
- `recommendation` should stay within the repository's review vocabulary
- `selected_for_digest=true` means the host agent explicitly chooses this paper for the final user-facing digest
- `selected_for_digest=false` means the paper may remain in ranked artifacts but should not appear in the final rendered digest

## Field semantics

### `reviewer_summary`

- Purpose: tell the user what the paper is actually doing.
- Form: 1-2 short sentences.
- Good style: compress the method, problem, and angle.
- Bad style: raw abstract copy, vague praise, or only restating the title.

### `why_it_matters`

- Purpose: tell the user why this paper is worth attention now.
- It should usually do one of these:
  - place the paper on an existing branch of the research map
  - explain what comparison value it adds
  - explain why it is a useful boundary-expanding adjacent paper
- It should not:
  - dump collection paths
  - restate Zotero evidence line by line
  - sound like a retrieval log

### `quick_takeaways`

- Purpose: allow fast scanning before reading the abstract.
- Prefer short phrases over long prose.
- Common shapes:
  - `method axis`
  - `problem setting`
  - `why to compare / keep`

### `zotero_comparison`

- Purpose: anchor the paper against the current Zotero library, especially nearest semantic neighbors.
- Preferred content:
  - `summary`: one short sentence saying what branch or line it is closest to
  - `related_items`: 1-2 nearby items when recoverable
- If only one clean neighbor is available, keep one.
- If two neighbors remain readable, keep two.
- If more than two make the card noisy, prefer the strongest one or two and summarize the branch in `summary`.

### `caveats`

- Purpose: record residual uncertainty, reading risk, or scope boundary.
- Good caveats:
  - profile-label mismatch risk
  - weak or indirect Zotero evidence
  - adjacent rather than central relevance
  - baseline / comparison value higher than novelty value
- Bad caveats:
  - generic hedging with no new information
  - repeating the recommendation in weaker words
  - placeholder warnings like “needs more study”

## Recommended agent inputs

- live profile JSON
- one candidate JSON
- matched interest labels
- ranking scores
- Zotero semantic or exact-search evidence when available

## Recommended agent outputs

The agent should emit a compact JSON patch rather than a full candidate rewrite.

Preferred target schema:

- `reports/schema/review-patch.schema.json`

The runtime can then merge the patch into the candidate artifact.
