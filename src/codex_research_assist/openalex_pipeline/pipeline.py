"""OpenAlex pipeline for NBER working papers."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .client import (
    NBER_PROGRAM_KEYWORDS,
    parse_paper,
    search_and_parse,
    search_nber_papers,
)

LOG = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "paper-finder" / "openalex"


def _cache_path(cache_dir: Path | None) -> Path:
    resolved = (cache_dir or DEFAULT_CACHE_DIR)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved / "cache.json"


def _meta_path(cache_dir: Path | None) -> Path:
    resolved = (cache_dir or DEFAULT_CACHE_DIR)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved / "meta.json"


def load_cache(cache_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load cached paper metadata."""
    path = _cache_path(cache_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        LOG.info("Loaded %d papers from cache", len(data))
        return data
    except Exception as exc:
        LOG.warning("Failed to load cache: %s", exc)
        return {}


def save_cache(cache: dict[str, dict[str, Any]], cache_dir: Path | None = None) -> None:
    """Persist cached paper metadata."""
    path = _cache_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("Saved %d papers to cache", len(cache))


def load_cache_meta(cache_dir: Path | None = None) -> dict[str, Any]:
    """Load cache metadata."""
    path = _meta_path(cache_dir)
    if not path.exists():
        return {"last_run_date": None, "total_fetched": 0, "runs": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"last_run_date": None, "total_fetched": 0, "runs": 0}


def save_cache_meta(meta: dict[str, Any], cache_dir: Path | None = None) -> None:
    """Persist cache metadata."""
    path = _meta_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def build_interest_query(interest: dict[str, Any]) -> dict[str, Any]:
    """Build OpenAlex query from interest config.

    Args:
        interest: Interest config dict with keywords, program, etc.

    Returns:
        Query dict for OpenAlex search
    """
    keywords = interest.get("keywords", [])
    program = interest.get("program")

    # Build search params
    params: dict[str, Any] = {
        "keywords": keywords,
    }

    if program:
        params["program"] = program

    return params


def run_search(
    interests: list[dict[str, Any]],
    cache_dir: Path | None = None,
    per_interest_limit: int = 10,
) -> dict[str, Any]:
    """Run search for all interests.

    Args:
        interests: List of interest configs
        cache_dir: Custom cache directory
        per_interest_limit: Max papers per interest

    Returns:
        Dict with search results
    """
    all_papers: list[dict[str, Any]] = []
    interest_results: dict[str, list[dict[str, Any]]] = {}

    for interest in interests:
        name = interest.get("name", "Unknown")
        keywords = interest.get("keywords", [])
        program = interest.get("program")
        from_date = interest.get("from_date")

        LOG.info(f"Searching interest: {name}")

        try:
            papers = search_and_parse(
                keywords=keywords,
                program=program,
                from_date=from_date,
                per_page=per_interest_limit,
            )

            interest_results[name] = papers
            all_papers.extend(papers)

            LOG.info(f"Found {len(papers)} papers for {name}")

        except Exception as exc:
            LOG.error(f"Failed to search {name}: {exc}")
            interest_results[name] = []

    return {
        "interests": interest_results,
        "all_papers": all_papers,
        "total": len(all_papers),
    }


def incremental_sync(
    cache_dir: Path | None = None,
    days_back: int = 30,
) -> dict[str, Any]:
    """Incrementally sync new papers since last run.

    Args:
        cache_dir: Custom cache directory
        days_back: Days to look back

    Returns:
        Sync result dict
    """
    meta = load_cache_meta(cache_dir)

    # Calculate date range
    from_date = meta.get("last_run_date")
    if not from_date:
        # First run - get last 30 days
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    else:
        # Incremental - just get new papers since last run
        from_date = from_date[:10]  # Extract YYYY-MM-DD

    to_date = datetime.now().strftime("%Y-%m-%d")

    LOG.info(f"Incremental sync from {from_date} to {to_date}")

    # Search without specific keywords - get all new papers
    papers = search_and_parse(
        from_date=from_date,
        per_page=50,
    )

    # Load existing cache
    cache = load_cache(cache_dir)

    # Add new papers to cache
    new_count = 0
    for paper in papers:
        nber_id = paper.get("nber_id")
        if nber_id and nber_id not in cache:
            cache[nber_id] = paper
            new_count += 1

    # Save cache and metadata
    save_cache(cache)

    meta["last_run_date"] = to_date
    meta["total_fetched"] = meta.get("total_fetched", 0) + new_count
    meta["runs"] = meta.get("runs", 0) + 1
    save_cache_meta(meta, cache_dir)

    return {
        "from_date": from_date,
        "to_date": to_date,
        "new_papers": new_count,
        "total_cached": len(cache),
    }


# Program keyword mapping export
__all__ = [
    "NBER_PROGRAM_KEYWORDS",
    "search_nber_papers",
    "search_and_parse",
    "parse_paper",
    "decode_abstract",
    "run_search",
    "incremental_sync",
    "load_cache",
    "save_cache",
]
