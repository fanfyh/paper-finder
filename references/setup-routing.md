# Interactive Agent Setup

Use this document during install or reconfiguration.

Goal:

- let the agent ask a small number of focused setup questions
- let the agent edit `config.json` directly
- avoid dumping the entire config surface into one message or one giant form
- make setup disappear after day 1 unless the user explicitly asks to revisit it

This is an interaction guide for the agent. It is not a script contract.

## Core rule

The agent should route by conversation, not by installer code.

That means:

1. inspect the user's goal
2. decide which option cluster matters
3. ask only the questions needed for that cluster
4. write or update `config.json`
5. summarize what was enabled and what stayed off

Once setup is complete:

- do not reopen the setup questionnaire during normal digest/search/render runs
- do not repeat dormant installation choices unless the user asks to reconfigure
- treat setup as background scaffolding, not as the main interaction surface

## Option clusters

### 1. Minimal digest

Use when the user only wants:

- arXiv retrieval
- profile-based ranking
- local HTML / markdown output

Ask:

1. where `profile_path` should live
2. where `output_root` should live
3. whether push delivery is needed now at all
4. how many top papers the host agent should enrich after retrieval
5. whether system fallback text should still be written before agent patches arrive

Usually do not ask about:

- Zotero API
- local `zotero.sqlite`
- feedback writeback

### 2. Zotero-backed profile refresh

Use when the user wants:

- profile refresh from live Zotero evidence
- library-scoped retrieval context

Ask:

1. `user` or `group` library
2. library id
3. whether the library scope should be enforced
4. whether profile basis should come from collections, tags, or both
5. whether delivery should stay local-only for now or route to email later

Ask for API key location only if the user actually wants live Zotero reads now.

### 3. Local semantic search

Use when the user wants:

- semantic search over local Zotero data
- better discovery than exact title/tag search

Ask:

1. local `zotero.sqlite` path
2. embedding backend or model string
3. whether semantic search should be enabled by default
4. whether the search should be limited to a specific local group/library id

Do not ask these questions if semantic search is not requested.

### 4. Agent-filled review

Use when the user wants:

- `Why it matters`
- recommendation text from the assistant perspective
- review notes that use profile context and later can use Zotero evidence

Ask:

1. how many top papers should be enriched first
2. how many papers may remain in the final visible digest
3. whether fallback to system text should remain enabled when agent review is unavailable

Important:

- agent-filled review is the default host-side behavior for digest enrichment
- the host agent should configure the supporting keys in `config.json`, then honor them in later runs

### 5. Email-first delivery

Use when the user wants direct delivery instead of only local artifacts.

Ask:

1. whether email should be the primary channel
2. sender address
3. recipients
4. SMTP host / port / auth method
5. whether HTML should be attached

Defaults:

- `delivery.primary_channel = "email"`
- keep `attach_digest_json = false` unless the user explicitly wants machine-readable attachments
- keep local HTML and metadata enabled

### 6. Telegram delivery

Use when the user wants push delivery rather than only local files.

Ask:

1. whether direct Telegram sending should be enabled
2. whether Telegram is the primary route or only a fallback/alternate route
3. whether local HTML and metadata files should still be written

If Telegram is off, keep local artifacts on by default.

### 7. Zotero feedback writeback

Use when the user wants post-review organization or non-destructive writeback.

Ask:

1. whether feedback writeback should be enabled at all
2. default tags
3. default collections
4. whether dry-run should remain the default behavior

## Question ordering

Ask in this order:

1. What outcome the user wants first: minimal digest, Zotero-backed refresh, semantic search, agent-filled review, email delivery, Telegram delivery, or feedback writeback.
2. Only the follow-up questions needed for the chosen outcome.
3. Confirm the resulting config changes in one compact summary.

## Config targets

The agent should usually edit these keys:

- `profile_path`
- `output_root`
- `review_generation.agent_top_n`
- `review_generation.final_top_n`
- `review_generation.fallback_to_system`
- `delivery.primary_channel`
- `delivery.email.*`
- `delivery.telegram.send_enabled`
- `zotero.*`
- `semantic_search.*`

The agent should not invent new config keys when an existing key already expresses the option.

## Output style for the agent

After editing config, the agent should summarize:

- what was enabled
- what stayed disabled
- which values still need secrets or local paths from the user

If something is not configured yet, say that directly instead of filling placeholders with guessed values.

Do not turn that summary into another setup round. Once the config is in place, move back to the user's actual literature task.
