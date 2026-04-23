# Zotero MCP Workflow

Use the bundled `paper-finder-zotero-mcp` server for live Zotero access.

## Primary Use Cases

### 1. Semantic library discovery

Recommended sequence:

1. Call `zotero_get_search_database_status`
2. If empty/stale, call `zotero_update_search_database`
3. Call `zotero_semantic_search` for discovery
4. Fall back to `zotero_search_items` for exact matches

### 2. Profile refresh

Recommended sequence:

1. Call `zotero_status`
2. Call `zotero_list_collections` if basis unknown
3. Call `zotero_profile_evidence`
4. Draft compact profile JSON
5. Call `zotero_write_profile` to write profile

### 3. Saving papers

Recommended sequence:

1. Assemble paper dicts from review output
2. Call `zotero_save_papers` with `dry_run=true`
3. Inspect plan for duplicates
4. Call `zotero_save_papers` with `dry_run=false`

### 4. Applying feedback

Recommended sequence:

1. Call `zotero_search_items` to resolve targets
2. Produce feedback JSON per schema
3. Call `zotero_apply_feedback` with `dry_run=true`
4. Inspect planned changes
5. Call `zotero_apply_feedback` with `dry_run=false`

### 5. Tag and collection organization

Recommended sequence:

1. Use `zotero_batch_update_tags` for tag edits
2. Use `zotero_create_collection` / `zotero_update_collection`
3. Use `zotero_move_items_to_collection` for membership

## Profile-writing Rules

- Zotero is primary evidence source
- Prefer 3-10 precise interest slices
- Keep each slice retrieval-friendly
- Preserve short method labels
- Do NOT dump long paragraph-style interests

## Writeback Rules

- Default to dry-run first
- Preserve user-created tags
- Never delete items or collections
- Prefer adding explanatory notes
