# Zotero MCP Workflow

Use the bundled `research-assist-zotero-mcp` server whenever the task needs live Zotero evidence or a Zotero writeback.

## Primary Use Cases

### 0. Semantic library discovery

Recommended sequence:

1. call `zotero_get_search_database_status`
2. if the database is empty or stale, call `zotero_update_search_database`
3. call `zotero_semantic_search` as the first-pass discovery tool
4. fall back to `zotero_search_items` for exact title / DOI / tag matches

### 1. Profile refresh

Recommended sequence:

1. call `zotero_status`
2. call `zotero_list_collections` if the configured basis is unknown
3. call `zotero_profile_evidence`
4. draft one compact profile JSON using `profiles/research-interest.example.json` as the contract example
5. call `zotero_write_profile` to write the normalized live profile

### 2. Saving newly selected papers

Recommended sequence:

1. assemble paper dicts from review output
2. call `zotero_save_papers` with `dry_run=true`
3. inspect the plan for duplicate / existing items
4. call `zotero_save_papers` with `dry_run=false` only after the plan looks correct

### 3. Applying user feedback

Recommended sequence:

1. call `zotero_search_items` to resolve the target items
2. produce one feedback JSON conforming to `reports/schema/zotero-feedback.schema.json`
3. call `zotero_apply_feedback` with `dry_run=true`
4. inspect the planned tags / collections / notes
5. call `zotero_apply_feedback` with `dry_run=false`

### 4. Tag and collection organization

Recommended sequence:

1. use `zotero_batch_update_tags` for broad tag edits
2. use `zotero_create_collection` / `zotero_update_collection` to manage collection structure
3. use `zotero_move_items_to_collection` to add/remove item membership in collections

Important boundary:

- `move_items_to_collection` changes Zotero collection membership
- it does not move attachment files inside the Zotero `storage/` directory

## Profile-writing rules

- treat Zotero as the primary evidence source
- prefer 3-10 precise interest slices
- keep each slice retrieval-friendly
- preserve short method labels
- do not dump long paragraph-style interests into the profile

## Writeback rules

- default to dry-run first
- preserve user-created tags unless there is explicit removal intent
- never delete items or collections
- prefer adding a note that explains the rationale for each writeback
