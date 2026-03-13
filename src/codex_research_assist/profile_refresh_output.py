from __future__ import annotations

import json
from typing import Any

from .arxiv_profile_pipeline.profile_contract import normalize_profile_payload


def parse_profile_refresh_output(raw_text: str) -> dict[str, Any]:
    if not isinstance(raw_text, str):
        raise ValueError("profile refresh output must be a string")

    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("profile refresh output must not be empty")
    if "```" in stripped:
        raise ValueError("profile refresh output must not use Markdown code fences")
    if not stripped.startswith("{"):
        raise ValueError("profile refresh output must start with '{'")
    if not stripped.endswith("}"):
        raise ValueError("profile refresh output must end with '}'")

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("profile refresh output must be valid JSON") from exc

    return normalize_profile_payload(payload)
