from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_sentence(text: str, *, max_length: int = 220) -> str | None:
    normalized = " ".join((text or "").split())
    if not normalized:
        return None
    parts = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
    sentence = parts[0].strip() if parts else normalized
    if len(sentence) <= max_length:
        return sentence
    return sentence[: max_length - 1].rstrip() + "..."


def _recommendation_from_scores(scores: dict[str, Any]) -> str:
    total = _as_float(scores.get("total"))
    map_match = _as_float(scores.get("map_match"))
    zotero_semantic = _as_float(scores.get("zotero_semantic"))

    if total >= 0.72 and map_match >= 0.55:
        return "read_first"
    if total >= 0.55 and map_match >= 0.40:
        return "skim"
    if map_match >= 0.28 or zotero_semantic >= 0.45:
        return "watch"
    return "skip_for_now"


def _recommendation_label(value: str) -> str:
    labels = {
        "read_first": "Read First",
        "skim": "Skim",
        "watch": "Watch",
        "skip_for_now": "Skip for now",
        "unset": "Unset",
    }
    return labels.get(value, value.replace("_", " ").title())


def _strongest_signal(scores: dict[str, Any]) -> str | None:
    components = {
        "map_match": _as_float(scores.get("map_match")),
        "zotero_semantic": _as_float(scores.get("zotero_semantic")),
    }
    signal_name, signal_value = max(components.items(), key=lambda item: item[1])
    if signal_value <= 0:
        return None
    labels = {
        "map_match": "research-map fit",
        "zotero_semantic": "zotero semantic affinity",
    }
    return labels[signal_name]


def build_system_review(candidate: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    paper = candidate.get("paper", {})
    triage = candidate.get("triage", {})
    scores = candidate.get("_scores", {})
    review = dict(candidate.get("review") or {})

    matched_labels = [str(label) for label in (triage.get("matched_interest_labels") or []) if str(label).strip()]
    recommendation = _recommendation_from_scores(scores)
    recommendation_label = _recommendation_label(recommendation)
    total = _as_float(scores.get("total"))
    map_match = _as_float(scores.get("map_match"))
    zotero_semantic = _as_float(scores.get("zotero_semantic"))

    why_parts: list[str] = []
    if matched_labels:
        if len(matched_labels) == 1:
            why_parts.append(f"Matches your active profile interest in {matched_labels[0]}.")
        else:
            why_parts.append(
                "Matches multiple active profile interests: " + ", ".join(matched_labels[:3]) + "."
            )
    elif profile is not None:
        why_parts.append("Retrieved as an exploratory paper; direct profile-match labels are weak.")
    else:
        why_parts.append("Profile context was not available when this digest note was generated.")

    if map_match >= 0.70:
        why_parts.append("Research-map fit is strong for the active profile slices.")
    elif map_match >= 0.45:
        why_parts.append("Research-map fit is moderate and worth a targeted skim.")
    else:
        why_parts.append("Research-map fit is limited, so treat this as lower-confidence triage.")

    if zotero_semantic >= 0.65:
        why_parts.append("It also sits close to existing Zotero literature in your library.")
    elif zotero_semantic > 0:
        why_parts.append("Zotero semantic evidence is present, but not especially concentrated.")
    why_parts.append(f"Current system recommendation: {recommendation_label}.")

    quick_takeaways: list[str] = [f"Recommendation: {recommendation_label}"]
    if matched_labels:
        quick_takeaways.append("Matched interests: " + ", ".join(matched_labels[:3]))
    strongest_signal = _strongest_signal(scores)
    if strongest_signal is not None:
        quick_takeaways.append(f"Strongest signal: {strongest_signal}")
    if total > 0:
        quick_takeaways.append(f"Ranking score: {total:.2f}")

    caveats: list[str] = []
    if not paper.get("abstract"):
        caveats.append("Abstract is missing, so the note is title-led.")
    if not matched_labels:
        caveats.append("No strong matched-interest label was attached to this candidate.")
    caveats.append("Zotero comparison has not been run in digest mode yet.")
    caveats.append("Recommendation is generated from profile labels and ranking signals, not full-text review.")

    review.update(
        {
            "review_status": "system_generated",
            "reviewer_summary": review.get("reviewer_summary") or _first_sentence(str(paper.get("abstract") or "")),
            "zotero_comparison": review.get("zotero_comparison")
            or {
                "status": "not_run",
                "summary": "Zotero comparison is not generated during digest rendering yet.",
                "related_items": [],
            },
            "recommendation": recommendation,
            "why_it_matters": " ".join(why_parts),
            "quick_takeaways": quick_takeaways,
            "caveats": caveats,
            "generation": {
                "mode": "system_profile_only",
                "sources": ["matched_interest_labels", "map_semantic_scores", "abstract_first_sentence"],
            },
        }
    )
    return review


def enrich_candidates_with_system_review(
    candidates: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    *,
    persist_json: bool = False,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate["review"] = build_system_review(candidate, profile)
        if persist_json:
            json_path = candidate.get("candidate", {}).get("json_path")
            if isinstance(json_path, str) and json_path:
                Path(json_path).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        enriched.append(candidate)
    return enriched
