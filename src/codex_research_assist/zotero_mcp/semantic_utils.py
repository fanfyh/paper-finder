from __future__ import annotations

import os


def is_local_mode() -> bool:
    """Return True if local Zotero mode is enabled.

    Local mode is enabled when `ZOTERO_LOCAL` is set to a truthy value:
    "true", "yes", or "1" (case-insensitive).
    """
    value = os.getenv("ZOTERO_LOCAL", "")
    return value.lower() in {"true", "yes", "1"}

