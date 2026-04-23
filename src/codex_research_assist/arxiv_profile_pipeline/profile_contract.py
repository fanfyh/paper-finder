from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _as_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _as_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        text = item.strip()
        if text:
            normalized.append(text)
    return normalized


def _as_int(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return value


def _dedupe_keep_order(items: list[str], *, limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(item)
        if limit is not None and len(result) >= limit:
            break
    return result


def _normalize_interest(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"interests[{index}] must be an object")
    logic = str(raw.get("logic") or "AND").upper()
    if logic not in {"AND", "OR"}:
        raise ValueError(f"interests[{index}].logic must be AND or OR")
    method_keywords = _as_string_list(raw.get("method_keywords"), f"interests[{index}].method_keywords")
    legacy_keywords = _as_string_list(raw.get("keywords"), f"interests[{index}].keywords")
    query_aliases = _as_string_list(raw.get("query_aliases"), f"interests[{index}].query_aliases")
    if not method_keywords and legacy_keywords:
        method_keywords = legacy_keywords
        query_aliases = [] if query_aliases else []
    normalized = {
        "interest_id": _as_string(raw.get("interest_id"), f"interests[{index}].interest_id"),
        "label": _as_string(raw.get("label"), f"interests[{index}].label"),
        "enabled": bool(raw.get("enabled", True)),
        "categories": _as_string_list(raw.get("categories"), f"interests[{index}].categories"),
        "method_keywords": _dedupe_keep_order(method_keywords, limit=2),
        "query_aliases": _dedupe_keep_order(query_aliases, limit=2),
        "exclude_keywords": _as_string_list(raw.get("exclude_keywords"), f"interests[{index}].exclude_keywords"),
        "logic": logic,
        "notes": str(raw.get("notes") or "").strip(),
    }
    if not normalized["method_keywords"]:
        raise ValueError(f"interests[{index}].method_keywords must not be empty")
    return normalized


def normalize_profile_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("profile payload must be a JSON object")

    zotero_basis_raw = raw.get("zotero_basis") or {}
    if not isinstance(zotero_basis_raw, dict):
        raise ValueError("zotero_basis must be an object")

    retrieval_defaults_raw = raw.get("retrieval_defaults") or {}
    if not isinstance(retrieval_defaults_raw, dict):
        raise ValueError("retrieval_defaults must be an object")

    updated_at = str(raw.get("updated_at") or "").strip() or datetime.now(UTC).isoformat()
    try:
        datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError("updated_at must be ISO 8601 date-time") from exc

    logic = str(retrieval_defaults_raw.get("logic") or "AND").upper()
    if logic not in {"AND", "OR"}:
        raise ValueError("retrieval_defaults.logic must be AND or OR")

    normalized = {
        "schema_version": str(raw.get("schema_version") or "1.1.0").strip() or "1.1.0",
        "profile_id": _as_string(raw.get("profile_id"), "profile_id"),
        "profile_name": _as_string(raw.get("profile_name"), "profile_name"),
        "updated_at": updated_at,
        "maintainer": str(raw.get("maintainer") or "paper-finder").strip() or "paper-finder",
        "zotero_basis": {
            "collections": _as_string_list(zotero_basis_raw.get("collections"), "zotero_basis.collections"),
            "tags": _as_string_list(zotero_basis_raw.get("tags"), "zotero_basis.tags"),
            "notes": str(zotero_basis_raw.get("notes") or "").strip(),
        },
        "retrieval_defaults": {
            "logic": logic,
            "sort_by": str(retrieval_defaults_raw.get("sort_by") or "lastUpdatedDate").strip() or "lastUpdatedDate",
            "sort_order": str(retrieval_defaults_raw.get("sort_order") or "descending").strip() or "descending",
            "since_days": _as_int(retrieval_defaults_raw.get("since_days", 7), "retrieval_defaults.since_days"),
            "max_results_per_interest": _as_int(
                retrieval_defaults_raw.get("max_results_per_interest", 10),
                "retrieval_defaults.max_results_per_interest",
                minimum=1,
            ),
            "max_pages": _as_int(retrieval_defaults_raw.get("max_pages", 10), "retrieval_defaults.max_pages", minimum=1),
            "state_path": str(retrieval_defaults_raw.get("state_path") or ".state/arxiv_profile_seen.json").strip()
            or ".state/arxiv_profile_seen.json",
        },
        "interests": [],
    }

    raw_interests = raw.get("interests")
    if not isinstance(raw_interests, list) or not raw_interests:
        raise ValueError("interests must be a non-empty list")
    normalized["interests"] = [_normalize_interest(item, index) for index, item in enumerate(raw_interests)]
    return normalized
