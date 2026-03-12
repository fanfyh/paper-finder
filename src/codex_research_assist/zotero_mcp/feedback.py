from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


ALLOWED_DECISIONS = {"archive", "watch", "read_first", "ignore", "unset"}
STATUS_TAG_PREFIX = "ra-status:"
SYSTEM_TAG = "research-assist"


def _as_string(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if value is None:
        if allow_empty:
            return ""
        raise ValueError(f"{field_name} must be a string")
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text and not allow_empty:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _as_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _as_string(item, f"{field_name}[{index}]")
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


@dataclass(frozen=True)
class FeedbackDecision:
    item_key: str | None
    doi: str | None
    title_contains: str | None
    decision: str
    rationale: str
    add_tags: tuple[str, ...]
    remove_tags: tuple[str, ...]
    add_collections: tuple[str, ...]
    remove_collections: tuple[str, ...]
    note_append: str


def _normalize_match(raw: Any, index: int) -> tuple[str | None, str | None, str | None]:
    if not isinstance(raw, dict):
        raise ValueError(f"decisions[{index}].match must be an object")
    item_key = _as_string(raw.get("item_key"), f"decisions[{index}].match.item_key", allow_empty=True) or None
    doi = _as_string(raw.get("doi"), f"decisions[{index}].match.doi", allow_empty=True) or None
    title_contains = _as_string(
        raw.get("title_contains"),
        f"decisions[{index}].match.title_contains",
        allow_empty=True,
    ) or None
    if not any([item_key, doi, title_contains]):
        raise ValueError(f"decisions[{index}].match must include item_key, doi, or title_contains")
    return item_key, doi.lower() if doi else None, title_contains


def normalize_feedback_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("feedback payload must be a JSON object")

    generated_at = _as_string(raw.get("generated_at"), "generated_at", allow_empty=True)
    if not generated_at:
        generated_at = datetime.now(UTC).isoformat()

    decisions_raw = raw.get("decisions")
    if not isinstance(decisions_raw, list) or not decisions_raw:
        raise ValueError("decisions must be a non-empty list")

    decisions: list[dict[str, Any]] = []
    for index, entry in enumerate(decisions_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"decisions[{index}] must be an object")
        item_key, doi, title_contains = _normalize_match(entry.get("match"), index)
        decision = _as_string(entry.get("decision"), f"decisions[{index}].decision").lower()
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(
                f"decisions[{index}].decision must be one of: {', '.join(sorted(ALLOWED_DECISIONS))}"
            )
        decisions.append(
            {
                "match": {
                    "item_key": item_key,
                    "doi": doi,
                    "title_contains": title_contains,
                },
                "decision": decision,
                "rationale": _as_string(entry.get("rationale"), f"decisions[{index}].rationale"),
                "add_tags": _as_string_list(entry.get("add_tags"), f"decisions[{index}].add_tags"),
                "remove_tags": _as_string_list(entry.get("remove_tags"), f"decisions[{index}].remove_tags"),
                "add_collections": _as_string_list(
                    entry.get("add_collections"),
                    f"decisions[{index}].add_collections",
                ),
                "remove_collections": _as_string_list(
                    entry.get("remove_collections"),
                    f"decisions[{index}].remove_collections",
                ),
                "note_append": _as_string(
                    entry.get("note_append"),
                    f"decisions[{index}].note_append",
                    allow_empty=True,
                ),
            }
        )

    return {
        "schema_version": str(raw.get("schema_version") or "1.0.0"),
        "generated_at": generated_at,
        "source": _as_string(raw.get("source"), "source", allow_empty=True) or "research-assist",
        "decisions": decisions,
    }


def decision_status_tag(decision: str) -> str | None:
    normalized = decision.strip().lower()
    if normalized == "unset":
        return None
    return f"{STATUS_TAG_PREFIX}{normalized}"


def build_feedback_note(decision: dict[str, Any], *, generated_at: str, source: str) -> str:
    lines = [
        "<p>research-assist feedback</p>",
        f"<p>time: {generated_at}</p>",
        f"<p>source: {source}</p>",
        f"<p>decision: {decision['decision']}</p>",
        f"<p>rationale: {decision['rationale']}</p>",
    ]
    if decision.get("note_append"):
        lines.append(f"<p>note: {decision['note_append']}</p>")
    if decision.get("add_tags"):
        lines.append(f"<p>add_tags: {', '.join(decision['add_tags'])}</p>")
    if decision.get("remove_tags"):
        lines.append(f"<p>remove_tags: {', '.join(decision['remove_tags'])}</p>")
    if decision.get("add_collections"):
        lines.append(f"<p>add_collections: {', '.join(decision['add_collections'])}</p>")
    if decision.get("remove_collections"):
        lines.append(f"<p>remove_collections: {', '.join(decision['remove_collections'])}</p>")
    return "\n".join(lines)
