from __future__ import annotations

import re
from collections import Counter


STOPWORDS = {
    "about",
    "across",
    "analysis",
    "approach",
    "based",
    "data",
    "from",
    "into",
    "model",
    "models",
    "method",
    "methods",
    "paper",
    "study",
    "studies",
    "system",
    "using",
    "with",
}


def _top_counter(counter: Counter[str], *, limit: int = 10, min_count: int = 1) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for key, count in counter.most_common():
        if count < min_count:
            continue
        result.append({"value": key, "count": count})
        if len(result) >= limit:
            break
    return result


def _extract_title_terms(title: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", title)
    result: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in STOPWORDS:
            continue
        result.append(lowered)
    return result


def build_profile_evidence_summary(
    items: list[dict],
    *,
    collections: list[str],
    tags: list[str],
    applied_limit: int,
) -> dict:
    tag_counter: Counter[str] = Counter()
    title_counter: Counter[str] = Counter()
    venue_counter: Counter[str] = Counter()
    year_counter: Counter[str] = Counter()

    for item in items:
        for tag in item.get("tags", []):
            tag_counter[tag] += 1
        for term in _extract_title_terms(str(item.get("title") or "")):
            title_counter[term] += 1
        venue = str(item.get("publication_title") or "").strip()
        if venue:
            venue_counter[venue] += 1
        year = str(item.get("year") or "").strip()
        if year:
            year_counter[year] += 1

    return {
        "basis": {
            "collections": collections,
            "tags": tags,
            "item_count": len(items),
            "applied_limit": applied_limit,
        },
        "summary": {
            "top_tags": _top_counter(tag_counter, limit=12, min_count=1),
            "top_title_terms": _top_counter(title_counter, limit=15, min_count=2),
            "top_publication_titles": _top_counter(venue_counter, limit=10, min_count=1),
            "top_years": _top_counter(year_counter, limit=10, min_count=1),
            "sample_titles": [item["title"] for item in items[:10] if item.get("title")],
        },
        "items": items,
    }
