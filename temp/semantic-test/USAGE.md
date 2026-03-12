# Local Semantic Test Usage

Private test credentials and machine-specific paths are stored in:

- `temp/private/zotero-test.env`

This file is git-ignored and is the only place where the current Zotero API key,
group id, and local `zotero.sqlite` path are stored for testing.

## Load the test environment

```bash
set -a
source /home/zlg/code/research-assist-zotero-wt/temp/private/zotero-test.env
set +a
```

## What the env file contains

- Zotero Web API credentials for the test group library
- Local sqlite path for semantic indexing
- Group/library restrictions used to keep tests inside the group library
- Temp model cache directory
- Temp Chroma persist directory
- The small local embedding model name intended for smoke tests

## Recommended smoke-test flow

1. Load `temp/private/zotero-test.env`
2. Ensure the test config references the same sqlite path and group scope
3. Install local semantic dependencies with `uv`
4. Build a very small index with a small `limit`
5. Run one semantic query

The env file is machine-specific. If any local path changes, update only
`temp/private/zotero-test.env`.
