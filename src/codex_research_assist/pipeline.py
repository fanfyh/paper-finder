"""OpenAlex retrieval pipeline for paper-finder.

Handles all paper retrieval from OpenAlex — journals and working-paper
institutions share the same pipeline, distinguished only by the ``source``
filter passed at call time.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .client import (
    NBER_PROGRAM_KEYWORDS,
    decode_abstract,
    parse_paper,
    search_and_parse,
    search_works,
)

LOG = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "paper-finder" / "openalex"


def _cache_path(cache_dir: Path | None) -> Path:
    resolved = cache_dir or DEFAULT_CACHE_DIR
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved / "cache.json"


def _meta_path(cache_dir: Path | None) -> Path:
    resolved = cache_dir or DEFAULT_CACHE_DIR
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
    """Build OpenAlex query from interest config."""
    keywords = interest.get("keywords", [])
    program = interest.get("program")
    params: dict[str, Any] = {"keywords": keywords}
    if program:
        params["program"] = program
    return params


def run_search(
    interests: list[dict[str, Any]],
    cache_dir: Path | None = None,
    per_interest_limit: int = 10,
) -> dict[str, Any]:
    """Run search for all interests."""
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
            LOG.error(f"Failed to search {name}: %s", exc)
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
    """Incrementally sync new papers since last run."""
    meta = load_cache_meta(cache_dir)

    from_date = meta.get("last_run_date")
    if not from_date:
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    else:
        from_date = from_date[:10]

    to_date = datetime.now().strftime("%Y-%m-%d")

    LOG.info(f"Incremental sync from {from_date} to {to_date}")

    papers = search_and_parse(from_date=from_date, per_page=50)

    cache = load_cache(cache_dir)

    new_count = 0
    for paper in papers:
        paper_id = paper.get("id", "")
        if paper_id and paper_id not in cache:
            cache[paper_id] = paper
            new_count += 1

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


# ── Candidate pipeline ──────────────────────────────────────────────────────────

OUTPUT_ROOT = Path.home() / "Documents" / "deadweight-notes" / "03_Resources" / "01_Raw_Literature"


def _convert_paper_to_candidate(paper: dict, interest: dict, source_type: str = "journal") -> dict:
    """Convert an OpenAlex paper dict to the candidate schema.

    Args:
        paper: Normalised paper dict from parse_paper().
        interest: Interest config that triggered this retrieval.
        source_type: "journal" or "working_paper". Determines how the venue
            and identifiers fields are populated.
    """
    paper_id = paper.get("id", "") or ""
    title = paper.get("title", "")
    authors = paper.get("authors", [])
    raw_abstract = paper.get("abstract", "")
    pub_date = paper.get("publication_date", "") or paper.get("published_at", "") or str(paper.get("year", "")) or ""

    if isinstance(raw_abstract, dict):
        abstract = decode_abstract(raw_abstract)
    elif isinstance(raw_abstract, str):
        abstract = raw_abstract
    else:
        abstract = str(raw_abstract) if raw_abstract else ""

    # authors from parse_paper() is already a list of strings; handle both formats
    author_list = []
    for a in authors:
        if isinstance(a, str):
            author_list.append(a)
        elif isinstance(a, dict):
            name = a.get("display_name") or (a.get("author", {}).get("display_name") if isinstance(a.get("author"), dict) else a.get("author", ""))
            if name:
                author_list.append(name)

    identifiers: dict[str, str] = {}
    doi = paper.get("doi", "")
    if doi:
        identifiers["doi"] = doi

    # Build source-specific fields
    if source_type == "working_paper":
        nber_id = paper.get("nber_id") or ""
        if nber_id:
            identifiers["nber_id"] = nber_id
        venue_label = "Working Paper"
        primary_category = "Working Paper"
        categories = ["Working Paper", "Economics"]
        pdf_url = f"https://www.nber.org/papers/{nber_id}.pdf" if nber_id else ""
        source_links = []
        if nber_id:
            source_links.append({"type": "pdf", "url": pdf_url})
            source_links.append({"type": "html", "url": f"https://www.nber.org/papers/{nber_id}"})
        source_name = "NBER"
    else:
        venue_label = paper.get("source_title", "") or "Journal"
        primary_category = venue_label
        categories = [venue_label] if venue_label else ["Journal"]
        pdf_url = paper.get("oa_url", "") or ""
        source_links = []
        if pdf_url:
            source_links.append({"type": "pdf", "url": pdf_url})
        source_name = venue_label

    year = pub_date[:4] if pub_date else ""
    interest_name = interest.get("label") or interest.get("name") or interest.get("interest_id", "")

    return {
        "schema_version": "2.0",
        "candidate": {
            "candidate_id": paper_id,
            "interest_name": interest_name,
            "interest_tags": interest.get("tags", []),
        },
        "source": {
            "source": "openalex",
            "source_type": source_type,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
        "paper": {
            "title": title,
            "authors": author_list,
            "venue": venue_label,
            "year": year,
            "primary_category": primary_category,
            "categories": categories,
            "published_at": pub_date,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "identifiers": identifiers,
            "source_links": source_links,
            "abstract": abstract,
            "abstract_source": "openalex",
            "pdf_url": pdf_url,
        },
        "triage": {"status": "pending", "assigned_to": None},
        "review": {"status": "pending"},
    }


def _generate_candidate_markdown(candidate: dict) -> str:
    """Generate Obsidian-friendly markdown for a candidate."""
    paper = candidate.get("paper", {})
    identifiers = paper.get("identifiers", {})
    source_links = paper.get("source_links", [])

    paper_id = identifiers.get("doi") or identifiers.get("nber_id") or ""
    title = paper.get("title", "Untitled")
    authors = paper.get("authors", [])
    abstract = paper.get("abstract", "")
    year = paper.get("year", "")
    pub_date = paper.get("published_at", "")
    venue = paper.get("venue", "")

    pdf_url = next((link.get("url", "") for link in source_links if link.get("type") == "pdf"), "")

    scores = candidate.get("_scores", {})
    map_match = scores.get("map_match", "-")
    zotero_semantic = scores.get("zotero_semantic", "-")
    total = scores.get("total", "-")

    interest_name = candidate.get("candidate", {}).get("interest_name", "")

    authors_quoted = ", ".join(f'"{a}"' for a in authors[:3])

    md_lines = [
        "---",
        f"title: \"{title}\"",
        f"authors: [{authors_quoted}]",
        f"year: {year}",
        f"publication_date: {pub_date}",
        f"venue: {venue}",
        f"generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"interest: {interest_name}",
        f"score: {total}",
        f"pdf_url: {pdf_url}",
        f"tags: [digest, {interest_name.lower().replace(' ', '-') if interest_name else 'uncategorized'}]",
        "---",
        "",
        f"# {title}",
        "",
        f"**Authors**: {', '.join(authors[:5])}{' et al.' if len(authors) > 5 else ''}",
        "",
        f"| 属性 | 信息 |",
        f"|------|------|",
        f"| **年份** | {year} |",
        f"| **发表日期** | {pub_date} |",
        f"| **期刊/来源** | {venue} |",
        f"| **匹配兴趣** | {interest_name} |",
    ]

    if scores:
        md_lines.extend([
            f"| **相关性得分** | **{total}** |",
            f"| - Map Match | {map_match} |",
            f"| - Zotero Semantic | {zotero_semantic} |",
        ])

    if pdf_url:
        md_lines.append(f"| **PDF** | [下载]({pdf_url}) |")

    md_lines.extend([
        "",
        f"> [!abstract]- **摘要**",
        f"> {abstract[:500]}{'...' if len(abstract) > 500 else ''}",
        "",
    ])

    return "\n".join(md_lines)


def run_openalex_pipeline(
    profile_path: Path | None = None,
    output_root: Path | None = None,
    source_filter: str | None = None,
    journal_sources: list[dict] | None = None,
    write_candidate_markdown_override: bool | None = None,
    since_days: int = 30,
    max_per_interest: int = 20,
    skip_keyword_filter: bool = False,
) -> dict:
    """Run OpenAlex retrieval pipeline.

    Fetches papers matching each interest in the profile, deduplicates,
    writes candidate JSON files, and produces a digest JSON manifest.

    Args:
        profile_path: Path to research interest profile JSON.
        output_root: Output directory for candidates and digest JSON.
                     Defaults to ~/Documents/deadweight-notes/.../Literature.
        source_filter: OpenAlex source alias or ID to filter by (e.g. "NBER",
                       "JPE", "SSRN"). None means unfiltered.
        journal_sources: List of dicts with ``openalex_id`` keys, e.g.
                       ``[{"openalex_id": "S199447588"}, ...]``.
                       When provided, uses multi-journal OR filter.
        since_days: Days to look back from today.
        max_per_interest: Max candidates per interest (per interest in keyword-filtered mode,
                          or total in skip_keyword_filter mode).
        skip_keyword_filter: If True, do NOT iterate over profile interests/keywords.
                             Instead do a single wide search (no keywords) across the
                             journal_sources, returning up to max_per_interest papers.
                             LLM scoring is then used to determine relevance.
        write_candidate_markdown_override: If False, skip writing .md files.
                                           If None or True, write them.

    Returns:
        Dict with digest_json_path and candidate_count.
    """
    profile: dict = {"interests": []}
    if profile_path and profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOG.warning("Failed to load profile: %s", exc)

    interests = profile.get("interests", [])

    # Extract list of OpenAlex source IDs from journal_sources
    source_ids: list[str] | None = None
    if journal_sources:
        source_ids = [j["openalex_id"] for j in journal_sources if j.get("openalex_id")]

    out_root = output_root or OUTPUT_ROOT
    out_root.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())[:8]
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")

    all_candidates: list[dict] = []

    journal_label = f"{len(source_ids)} journals" if source_ids else str(source_filter)
    from_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")

    if skip_keyword_filter:
        # Wide mode: pull papers without keyword filter, let LLM determine relevance
        LOG.info("Running OpenAlex pipeline in WIDE mode (source=%s, since_days=%d)", journal_label, since_days)
        try:
            papers = search_and_parse(
                keywords=[],  # no keyword filter
                from_date=from_date,
                per_page=max_per_interest,
                source_ids=source_ids,
                source=source_filter if not source_ids else None,
            )
            LOG.info("Wide retrieval returned %d papers", len(papers))
            # Attach a dummy interest to maintain candidate schema
            dummy_interest = {
                "interest_id": "__wide__",
                "label": "Wide Retrieval (LLM-scored)",
            }
            for paper in papers:
                candidate = _convert_paper_to_candidate(paper, dummy_interest, source_type="journal")
                all_candidates.append(candidate)
        except Exception as exc:
            LOG.error("Wide retrieval failed: %s", exc)
    else:
        # Standard keyword-filtered mode
        LOG.info("Running OpenAlex pipeline with %d interests (source=%s)", len(interests), journal_label)

        for interest in interests:
            name = interest.get("label") or interest.get("name") or interest.get("interest_id", "Unknown")
            keywords = interest.get("keywords", []) or interest.get("method_keywords", [])
            if not keywords:
                keywords = interest.get("query_aliases", [])
            LOG.info("Processing interest: %s (keywords: %s)", name, keywords[:3])

            try:
                papers = search_and_parse(
                    keywords=keywords,
                    from_date=from_date,
                    per_page=max_per_interest,
                    source_ids=source_ids,
                    source=source_filter if not source_ids else None,
                )
                for paper in papers:
                    source_type = "working_paper" if source_filter in ("NBER", "SSRN", "CEPR") else "journal"
                    candidate = _convert_paper_to_candidate(paper, interest, source_type=source_type)
                    all_candidates.append(candidate)
            except Exception as exc:
                LOG.error("Failed to process interest %s: %s", name, exc)

    # Deduplicate by paper ID (keep first seen)
    seen_ids: set = set()
    unique_candidates: list[dict] = []
    for c in all_candidates:
        pid = c.get("paper", {}).get("identifiers", {}).get("doi") or c.get("paper", {}).get("identifiers", {}).get("nber_id") or ""
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_candidates.append(c)

    # Write candidate JSON + optional markdown
    candidate_paths: list[str] = []
    candidate_markdown_paths: list[str] = []

    for candidate in unique_candidates:
        pid = candidate.get("paper", {}).get("identifiers", {}).get("doi") or candidate.get("paper", {}).get("identifiers", {}).get("nber_id", "")
        if not pid:
            pid = candidate.get("paper", {}).get("id", "")
        if not pid:
            continue

        safe_pid = pid.replace("/", "_")
        json_path = out_root / f"{date_str}-{safe_pid}.json"
        json_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        candidate_paths.append(str(json_path))

        if write_candidate_markdown_override is not False:
            md_content = _generate_candidate_markdown(candidate)
            md_path = out_root / f"{date_str}-{safe_pid}.md"
            md_path.write_text(md_content, encoding="utf-8")
            candidate_markdown_paths.append(str(md_path))

    # Write main digest JSON
    digest_data = {
        "schema_version": "2.0",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": "openalex",
        "profile_id": profile.get("id", "default"),
        "profile_name": profile.get("name", "Research Interests"),
        "profile_path": str(profile_path) if profile_path else None,
        "source_filter": source_filter,
        "query_manifest": [
            {"interest": i.get("name"), "keywords": i.get("keywords", [])} for i in interests
        ],
        "candidate_count": len(unique_candidates),
        "candidate_paths": candidate_paths,
        "candidate_markdown_paths": candidate_markdown_paths,
    }

    digest_json_path = out_root / f"{date_str}.json"
    digest_json_path.write_text(json.dumps(digest_data, ensure_ascii=False, indent=2), encoding="utf-8")

    LOG.info("OpenAlex pipeline complete: %d candidates", len(unique_candidates))

    return {
        "digest_json_path": str(digest_json_path),
        "candidate_count": len(unique_candidates),
    }


# Public API
__all__ = [
    "NBER_PROGRAM_KEYWORDS",
    "search_and_parse",
    "search_works",
    "parse_paper",
    "run_search",
    "incremental_sync",
    "load_cache",
    "save_cache",
    "run_openalex_pipeline",
    "_generate_candidate_markdown",
]
