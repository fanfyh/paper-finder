"""
Lightweight scoring and ranking for arXiv candidates.

Scoring formula:
  score = relevance(0.60) + recency(0.25) + novelty(0.15)

Each component is normalized to [0, 1] then multiplied by its weight.
"""
from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timezone


def _tokenize(text: str) -> set[str]:
    """Lowercase split + strip punctuation."""
    return set(re.findall(r"[a-z0-9]{2,}", text.lower()))


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp to UTC datetime."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def score_relevance(candidate: dict, profile: dict) -> float:
    """
    Keyword overlap between paper and profile interests.

    Each keyword phrase (method_keywords and query_aliases) is scored
    independently against the paper text. The best match across all
    phrases and all interests is returned.
    """
    paper = candidate.get("paper", {})
    paper_tokens = _tokenize(
        " ".join([
            paper.get("title", ""),
            paper.get("abstract", ""),
            " ".join(paper.get("categories", [])),
        ])
    )

    if not paper_tokens:
        return 0.0

    best = 0.0
    interests = profile.get("interests", [])

    for interest in interests:
        if not interest.get("enabled", True):
            continue

        # Score each keyword phrase independently to avoid dilution
        all_phrases = list(interest.get("method_keywords", [])) + list(interest.get("query_aliases", []))
        for phrase in all_phrases:
            phrase_tokens = _tokenize(phrase)
            if not phrase_tokens:
                continue
            overlap = len(paper_tokens & phrase_tokens)
            score = min(overlap / len(phrase_tokens), 1.0)
            best = max(best, score)

    return min(best, 1.0)


def score_recency(candidate: dict, now: datetime | None = None) -> float:
    """
    Time-based score with exponential decay.

    - last 7 days  -> 1.0
    - older        -> exponential decay from 1.0
    """
    if now is None:
        now = datetime.now(timezone.utc)

    paper = candidate.get("paper", {})

    # Try updated_at first, then published_at
    timestamp = _parse_timestamp(paper.get("updated_at"))
    if timestamp is None:
        timestamp = _parse_timestamp(paper.get("published_at"))

    if timestamp is None:
        return 0.5  # Unknown date gets neutral score

    age_days = max(0, (now - timestamp).total_seconds() / 86400)

    if age_days <= 7:
        return 1.0

    # Exponential decay: score = exp(-lambda * (age - 7))
    # lambda = 0.01 gives ~0.5 at 76 days, ~0.1 at 237 days
    decay_rate = 0.01
    score = math.exp(-decay_rate * (age_days - 7))
    return max(score, 0.0)


def score_novelty(candidate: dict, history_ids: set[str]) -> float:
    """
    Novelty score based on whether paper was seen before.

    Returns 1.0 if not in history, 0.0 if already seen.
    """
    paper = candidate.get("paper", {})
    arxiv_id = paper.get("identifiers", {}).get("arxiv_id", "")

    if not arxiv_id:
        return 0.5  # Unknown ID gets neutral score

    return 0.0 if arxiv_id in history_ids else 1.0


def rank_candidates(
    candidates: list[dict],
    profile: dict,
    history_ids: set[str],
    *,
    w_relevance: float = 0.60,
    w_recency: float = 0.25,
    w_novelty: float = 0.15,
) -> list[dict]:
    """
    Score and rank candidates by weighted sum of components.

    Returns a new sorted list (highest score first) with _scores field added.
    Does not mutate the input candidates.
    """
    now = datetime.now(timezone.utc)
    scored: list[dict] = []

    for candidate in candidates:
        rel = score_relevance(candidate, profile)
        rec = score_recency(candidate, now)
        nov = score_novelty(candidate, history_ids)

        total = (w_relevance * rel) + (w_recency * rec) + (w_novelty * nov)

        candidate_copy = copy.deepcopy(candidate)
        candidate_copy["_scores"] = {
            "relevance": round(rel, 4),
            "recency": round(rec, 4),
            "novelty": round(nov, 4),
            "total": round(total, 4),
        }
        scored.append(candidate_copy)

    scored.sort(key=lambda x: x["_scores"]["total"], reverse=True)
    return scored
