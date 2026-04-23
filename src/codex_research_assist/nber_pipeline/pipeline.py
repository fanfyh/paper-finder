"""NBER pipeline using OpenAlex API.

Replaces the old NBER API-based pipeline with OpenAlex for better search.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..openalex_pipeline import (
    NBER_PROGRAM_KEYWORDS,
    search_and_parse,
)

LOG = logging.getLogger(__name__)

DEFAULT_OUTPUT_ROOT = Path.home() / "Documents" / "deadweight-notes" / "03_Resources" / "01_Raw_Literature" / "NBER"


def run_nber_pipeline(
    config_path: Path | None = None,
    profile_path: Path | None = None,
    write_candidate_markdown_override: bool | None = None,
    output_root: Path | None = None,
    since_days: int = 30,
    max_per_interest: int = 20,
) -> dict[str, Any]:
    """Run NBER pipeline using OpenAlex API.

    Args:
        config_path: Path to config.json (unused, kept for compatibility)
        profile_path: Path to research interest profile
        write_candidate_markdown_override: Whether to write markdown
        output_root: Output directory
        since_days: Days to look back
        max_per_interest: Max candidates per interest

    Returns:
        Dict with paths and candidate count
    """
    # Load profile
    profile = {"interests": []}
    if profile_path and profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOG.warning("Failed to load profile: %s", exc)

    interests = profile.get("interests", [])

    # Use default output root
    out_root = output_root or DEFAULT_OUTPUT_ROOT
    out_root.mkdir(parents=True, exist_ok=True)

    # Generate run ID
    run_id = str(uuid.uuid4())[:8]
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")

    # Collect all candidates
    all_candidates = []
    candidate_paths = []
    candidate_markdown_paths = []

    LOG.info("Running NBER pipeline with %d interests", len(interests))

    for interest in interests:
        # Handle different profile formats
        name = interest.get("label") or interest.get("name") or interest.get("interest_id", "Unknown")
        keywords = interest.get("keywords", []) or interest.get("method_keywords", [])
        # Also check query_aliases
        if not keywords:
            keywords = interest.get("query_aliases", [])
        program = interest.get("program")
        from_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")

        LOG.info("Processing interest: %s (keywords: %s)", name, keywords[:3])

        try:
            papers = search_and_parse(
                keywords=keywords,
                program=program,
                from_date=from_date,
                per_page=max_per_interest,
            )

            for paper in papers:
                candidate = _convert_paper_to_candidate(paper, interest)
                all_candidates.append(candidate)

        except Exception as exc:
            LOG.error("Failed to process interest %s: %s", name, exc)

    # Deduplicate by NBER ID - keep only latest
    seen_ids = set()
    unique_candidates = []
    for c in all_candidates:
        nber_id = c.get("paper", {}).get("identifiers", {}).get("nber_id", "")
        if nber_id and nber_id not in seen_ids:
            seen_ids.add(nber_id)
            unique_candidates.append(c)

    # Clean up old files for these NBER IDs
    for candidate in unique_candidates:
        nber_id = candidate.get("paper", {}).get("identifiers", {}).get("nber_id", "")
        if nber_id:
            # Delete old versions (files with same nber_id but different date prefix)
            for old_file in out_root.glob(f"*-{nber_id}.json"):
                if old_file.name != f"{date_str}-{nber_id}.json":
                    old_file.unlink()
                    LOG.info("Removed old file: %s", old_file.name)
            for old_file in out_root.glob(f"*-{nber_id}.md"):
                if old_file.name != f"{date_str}-{nber_id}.md":
                    old_file.unlink()
                    LOG.info("Removed old file: %s", old_file.name)

    # Write candidate JSON files
    for candidate in unique_candidates:
        nber_id = candidate.get("paper", {}).get("identifiers", {}).get("nber_id", "")
        if not nber_id:
            continue

        json_path = out_root / f"{date_str}-{nber_id}.json"
        json_path.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        candidate_paths.append(str(json_path))

        # Write markdown
        if write_candidate_markdown_override is not False:
            md_content = _generate_candidate_markdown(candidate)
            md_path = out_root / f"{date_str}-{nber_id}.md"
            md_path.write_text(md_content, encoding="utf-8")
            candidate_markdown_paths.append(str(md_path))

    # Write main digest JSON
    digest_data = {
        "schema_version": "2.0",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": "nber-openalex",
        "profile_id": profile.get("id", "default"),
        "profile_name": profile.get("name", "Research Interests"),
        "profile_path": str(profile_path) if profile_path else None,
        "query_manifest": [
            {"interest": i.get("name"), "keywords": i.get("keywords", []), "program": i.get("program")}
            for i in interests
        ],
        "candidate_count": len(unique_candidates),
        "candidate_paths": candidate_paths,
        "candidate_markdown_paths": candidate_markdown_paths,
    }

    digest_json_path = out_root / f"{date_str}.json"
    digest_json_path.write_text(
        json.dumps(digest_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    LOG.info("NBER pipeline complete: %d candidates", len(unique_candidates))

    return {
        "digest_json_path": str(digest_json_path),
        "candidate_count": len(unique_candidates),
    }


def _convert_paper_to_candidate(paper: dict[str, Any], interest: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAlex paper to candidate format."""
    nber_id = paper.get("nber_id", "")
    title = paper.get("title", "")
    authors = paper.get("authors", [])
    abstract = paper.get("abstract", "")
    pub_date = paper.get("publication_date", "")
    cited_by = paper.get("cited_by_count", 0)

    # Format authors
    author_list = [a.get("name", "") for a in authors if a.get("name")]

    # Build identifiers
    identifiers = {
        "nber_id": nber_id,
    }
    doi = paper.get("doi", "")
    if doi:
        identifiers["doi"] = doi

    # Build source links
    source_links = []
    pdf_url = f"https://www.nber.org/papers/{nber_id}.pdf" if nber_id else ""
    if pdf_url:
        source_links.append({"type": "pdf", "url": pdf_url})

    nber_url = f"https://www.nber.org/papers/{nber_id}" if nber_id else ""
    if nber_url:
        source_links.append({"type": "html", "url": nber_url})

    # Extract year
    year = pub_date[:4] if pub_date else ""

    interest_name = interest.get("label") or interest.get("name") or interest.get("interest_id", "")

    return {
        "schema_version": "2.0",
        "candidate": {
            "candidate_id": nber_id,
            "interest_name": interest_name,
            "interest_tags": interest.get("tags", []),
        },
        "source": {
            "source": "nber-openalex",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
        "paper": {
            "title": title,
            "authors": author_list,
            "venue": "NBER Working Paper",
            "year": year,
            "primary_category": "NBER",
            "categories": ["NBER", "Economics"],
            "published_at": pub_date,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "identifiers": identifiers,
            "source_links": source_links,
            "abstract": abstract,
            "abstract_source": "openalex",
            "pdf_url": pdf_url,
        },
        "triage": {
            "status": "pending",
            "assigned_to": None,
        },
        "review": {
            "status": "pending",
        },
    }


def _generate_candidate_markdown(candidate: dict[str, Any]) -> str:
    """Generate markdown for a candidate."""
    paper = candidate.get("paper", {})
    identifiers = paper.get("identifiers", {})
    source_links = paper.get("source_links", [])

    nber_id = identifiers.get("nber_id", "")
    title = paper.get("title", "Untitled")
    authors = paper.get("authors", [])
    abstract = paper.get("abstract", "")
    year = paper.get("year", "")
    pub_date = paper.get("published_at", "")

    # Get PDF URL
    pdf_url = ""
    for link in source_links:
        if link.get("type") == "pdf":
            pdf_url = link.get("url", "")
            break

    # Get scores if available
    scores = candidate.get("_scores", {})
    map_match = scores.get("map_match", "-")
    zotero_semantic = scores.get("zotero_semantic", "-")
    total = scores.get("total", "-")

    # Get interest info
    cand_info = candidate.get("candidate", {})
    interest_name = cand_info.get("interest_name", "")

    md_lines = [
        f"---",
        f"nber_id: {nber_id}",
        f"title: \"{title}\"",
        f"authors: [{', '.join([f'\"{a}\"' for a in authors[:3]])}]",
        f"year: {year}",
        f"publication_date: {pub_date}",
        f"generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"interest: {interest_name}",
        f"score: {total}",
        f"pdf_url: {pdf_url}",
        f"tags: [nber, digest, {interest_name.lower().replace(' ', '-') if interest_name else 'uncategorized'}]",
        f"cssclass: [nber-digest]",
        f"---",
        "",
        f"# {title}",
        "",
        f"**Authors**: {', '.join(authors[:5])}{' et al.' if len(authors) > 5 else ''}",
        "",
        f"| 属性 | 信息 |",
        f"|------|------|",
        f"| **NBER ID** | `{nber_id}` |",
        f"| **年份** | {year} |",
        f"| **发布日期** | {pub_date} |",
        f"| **匹配兴趣** | {interest_name} |",
    ]

    # Add scores if available
    if scores:
        md_lines.extend([
            f"| **相关性得分** | **{total}** |",
            f"| - Map Match | {map_match} |",
            f"| - Zotero Semantic | {zotero_semantic} |",
        ])

    md_lines.extend([
        f"| **PDF** | [下载]({pdf_url}) |",
        "",
        f"> [!abstract]- **摘要**",
        f"> {abstract[:500]}{'...' if len(abstract) > 500 else ''}",
        "",
    ])

    return "\n".join(md_lines)


__all__ = ["run_nber_pipeline"]
