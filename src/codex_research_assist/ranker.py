"""
Two-factor ranking for arXiv candidates.

Scoring formula:
  total = map_match(0.30) + zotero_semantic(0.70)

- map_match: how well the paper fits the current research map slices
- zotero_semantic: how close the paper is to nearby Zotero literature

Soft guard:
- if map_match < 0.30, apply a penalty to avoid semantic-only false positives
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any, Callable


SemanticSearchFn = Callable[[str, int], dict[str, Any]]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", text.lower()))


def _candidate_id(candidate: dict[str, Any], fallback_index: int) -> str:
    candidate_block = candidate.get("candidate", {})
    candidate_id = candidate_block.get("candidate_id")
    if isinstance(candidate_id, str) and candidate_id.strip():
        return candidate_id
    return f"candidate-{fallback_index}"


def _paper_tokens(candidate: dict[str, Any]) -> set[str]:
    paper = candidate.get("paper", {})
    return _tokenize(
        " ".join(
            [
                str(paper.get("title") or ""),
                str(paper.get("abstract") or ""),
                " ".join(str(category) for category in (paper.get("categories") or [])),
            ]
        )
    )


def _phrase_score(paper_tokens: set[str], phrases: list[str]) -> float:
    best = 0.0
    for phrase in phrases:
        phrase_tokens = _tokenize(phrase)
        if not phrase_tokens:
            continue
        overlap = len(paper_tokens & phrase_tokens)
        best = max(best, min(overlap / len(phrase_tokens), 1.0))
    return min(best, 1.0)


def _candidate_interest_ids(candidate: dict[str, Any]) -> set[str]:
    triage = candidate.get("triage", {})
    return {
        str(value).strip()
        for value in (triage.get("matched_interest_ids") or [])
        if str(value).strip()
    }


def score_map_match(candidate: dict[str, Any], profile: dict[str, Any]) -> float:
    """
    Score against the active research-map slices rather than global lexical overlap.

    Each interest contributes:
    - method keyword fit
    - alias fit
    - category fit
    """
    paper_tokens = _paper_tokens(candidate)
    if not paper_tokens:
        return 0.0

    paper_categories = {
        str(category).strip().lower()
        for category in (candidate.get("paper", {}).get("categories") or [])
        if str(category).strip()
    }
    matched_interest_ids = _candidate_interest_ids(candidate)

    best = 0.0
    for interest in profile.get("interests", []):
        if not interest.get("enabled", True):
            continue
        interest_id = str(interest.get("interest_id") or "").strip()
        if matched_interest_ids and interest_id and interest_id not in matched_interest_ids:
            continue

        method_score = _phrase_score(paper_tokens, list(interest.get("method_keywords") or []))
        alias_score = _phrase_score(paper_tokens, list(interest.get("query_aliases") or []))
        interest_categories = {
            str(category).strip().lower()
            for category in (interest.get("categories") or [])
            if str(category).strip()
        }
        category_score = 1.0 if paper_categories.intersection(interest_categories) else 0.0

        interest_score = (0.65 * method_score) + (0.20 * alias_score) + (0.15 * category_score)
        best = max(best, interest_score)

    return round(min(best, 1.0), 4)


def _semantic_query(candidate: dict[str, Any]) -> str:
    paper = candidate.get("paper", {})
    title = " ".join(str(paper.get("title") or "").split())
    abstract = " ".join(str(paper.get("abstract") or "").split())
    if abstract:
        return f"{title}. {abstract[:800]}"
    return title


def _distance_to_affinity(distance: float | None) -> float:
    if not isinstance(distance, (int, float)):
        return 0.0
    return 1.0 / (1.0 + max(float(distance), 0.0))


def _normalize_semantic_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    if not raw_scores:
        return {}
    values = list(raw_scores.values())
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value, rel_tol=1e-9, abs_tol=1e-9):
        return {candidate_id: round(values[0], 4) for candidate_id in raw_scores}
    normalized: dict[str, float] = {}
    span = max_value - min_value
    for candidate_id, raw_value in raw_scores.items():
        normalized[candidate_id] = round((raw_value - min_value) / span, 4)
    return normalized


def collect_zotero_semantic_scores(
    candidates: list[dict[str, Any]],
    *,
    semantic_search_fn: SemanticSearchFn | None,
    semantic_limit: int = 3,
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    if semantic_search_fn is None:
        return {}, {}

    raw_scores: dict[str, float] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates):
        candidate_id = _candidate_id(candidate, index)
        try:
            payload = semantic_search_fn(_semantic_query(candidate), semantic_limit)
        except Exception:
            continue
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not results:
            evidence[candidate_id] = {"count": 0, "best_distance": None}
            continue
        distances = [
            float(result["distance"])
            for result in results
            if isinstance(result.get("distance"), (int, float))
        ]
        best_distance = min(distances) if distances else None
        raw_scores[candidate_id] = _distance_to_affinity(best_distance)
        neighbors: list[dict[str, Any]] = []
        for result in results:
            metadata = result.get("metadata") or {}
            neighbors.append(
                {
                    "item_key": result.get("item_key"),
                    "title": metadata.get("title"),
                    "collections": metadata.get("collections"),
                    "distance": result.get("distance"),
                }
            )
        evidence[candidate_id] = {
            "count": len(results),
            "best_distance": best_distance,
            "top_item_key": results[0].get("item_key"),
            "top_title": (results[0].get("metadata") or {}).get("title"),
            "neighbors": neighbors,
        }
    return _normalize_semantic_scores(raw_scores), evidence


def rank_candidates(
    candidates: list[dict[str, Any]],
    profile: dict[str, Any],
    history_ids: set[str] | None = None,
    *,
    semantic_search_fn: SemanticSearchFn | None = None,
    semantic_limit: int = 3,
    w_map_match: float = 0.30,
    w_zotero_semantic: float = 0.70,
    min_map_match: float = 0.30,
    low_map_penalty: float = 0.75,
) -> list[dict[str, Any]]:
    """
    Rank by research-map fit plus Zotero semantic affinity.

    history_ids is kept only for API compatibility with older call sites.
    """
    del history_ids

    semantic_scores, semantic_evidence = collect_zotero_semantic_scores(
        candidates,
        semantic_search_fn=semantic_search_fn,
        semantic_limit=semantic_limit,
    )
    semantic_available = bool(semantic_scores)

    scored: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        candidate_copy = copy.deepcopy(candidate)
        candidate_id = _candidate_id(candidate_copy, index)
        map_match = score_map_match(candidate_copy, profile)
        zotero_semantic = semantic_scores.get(candidate_id, 0.0)

        if semantic_available:
            total = (w_map_match * map_match) + (w_zotero_semantic * zotero_semantic)
        else:
            total = map_match
        penalty_applied = False
        if map_match < min_map_match:
            total *= low_map_penalty
            penalty_applied = True

        evidence = semantic_evidence.get(candidate_id, {})
        candidate_copy["_scores"] = {
            "map_match": round(map_match, 4),
            "zotero_semantic": round(zotero_semantic, 4),
            "total": round(total, 4),
            "model": "map_semantic_v1",
            "weights": {
                "map_match": round(w_map_match, 4),
                "zotero_semantic": round(w_zotero_semantic, 4) if semantic_available else 0.0,
            },
            "min_map_match": round(min_map_match, 4),
            "low_map_penalty": round(low_map_penalty, 4),
            "penalty_applied": penalty_applied,
            "semantic_available": semantic_available,
            "semantic_best_distance": evidence.get("best_distance"),
            "semantic_neighbor_count": evidence.get("count", 0),
            "semantic_top_item_key": evidence.get("top_item_key"),
            "semantic_top_title": evidence.get("top_title"),
            "semantic_neighbors": evidence.get("neighbors", []),
        }
        scored.append(candidate_copy)

    scored.sort(key=lambda item: item["_scores"]["total"], reverse=True)
    return scored
