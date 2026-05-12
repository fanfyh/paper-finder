#!/usr/bin/env python3
"""Manual journal digest: 30-day papers from configured journals, LLM-scored and ranked."""
from __future__ import annotations
import json, logging, sys, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codex_research_assist.client import search_and_parse, decode_abstract
from codex_research_assist.llm_scorer import score_papers_llm, add_llm_scores_to_candidates
from codex_research_assist.pipeline import _convert_paper_to_candidate
from codex_research_assist.html_fmt import format_digest_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
LOG = logging.getLogger("manual_journal_digest")

CONFIG_PATH = Path.home() / ".claude/tools/paper-finder/config.json"
PROFILE_PATH = Path.home() / ".claude/tools/paper-finder/profiles/research-interest.json"
REPORTS_DIR = Path.home() / ".claude/tools/paper-finder/reports/viewer"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    config = load_json(CONFIG_PATH)
    profile = load_json(PROFILE_PATH)
    journal_sources = config.get("retrieval", {}).get("journal_sources", [])
    interests = profile.get("interests", [])

    since_days = 30
    from_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    LOG.info("Searching %d journals from %s", len(journal_sources), from_date)

    all_candidates = []
    source_ids = [j["openalex_id"] for j in journal_sources if j.get("openalex_id")]
    LOG.info("Source IDs: %s", source_ids)

    # Pull up to 20 papers per journal
    for j in journal_sources:
        title = j.get("title", "?")
        sid = j.get("openalex_id", "")
        LOG.info("Searching: %s (%s)", title, sid)
        try:
            papers = search_and_parse(
                keywords=[],
                from_date=from_date,
                per_page=20,
                source_ids=[sid] if sid else None,
                source=None,
            )
            LOG.info("  -> %d papers", len(papers))
            dummy_interest = {"interest_id": "__journal__", "label": title}
            for paper in papers:
                candidate = _convert_paper_to_candidate(paper, dummy_interest, source_type="journal")
                all_candidates.append(candidate)
        except Exception as e:
            LOG.warning("Failed %s: %s", title, e)

    LOG.info("Total candidates before dedup: %d", len(all_candidates))

    # Deduplicate by DOI
    seen = set()
    unique = []
    for c in all_candidates:
        pid = c.get("paper", {}).get("identifiers", {}).get("doi", "")
        if pid and pid not in seen:
            seen.add(pid)
            unique.append(c)
    LOG.info("Total unique: %d", len(unique))

    if not unique:
        LOG.error("No papers found!")
        return

    # LLM score all papers (interest-aware)
    LOG.info("Running LLM scoring for %d papers...", len(unique))
    scored = add_llm_scores_to_candidates(unique, interests)

    # Sort by LLM relevance score descending
    scored.sort(key=lambda c: c.get("_scores", {}).get("llm_relevance", 0), reverse=True)

    # Build viewer JSON
    viewer_papers = []
    for c in scored:
        paper = c.get("paper", {})
        scores = c.get("_scores", {})
        identifiers = paper.get("identifiers", {})
        url = identifiers.get("doi", "")
        if not url:
            source_links = paper.get("source_links", [])
            url = next((l["url"] for l in source_links if l.get("type") == "pdf"), "")

        viewer_papers.append({
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "venue": paper.get("venue", ""),
            "year": paper.get("year", ""),
            "published_at": paper.get("published_at", ""),
            "abstract": paper.get("abstract", ""),
            "url": url,
            "doi": identifiers.get("doi", ""),
            "cited_by_count": 0,
            "relevance": scores.get("llm_relevance", 0),
            "interest_name": c.get("candidate", {}).get("interest_name", ""),
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    viewer_path = REPORTS_DIR / "papers_data.json"
    viewer_path.write_text(json.dumps(viewer_papers, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("Wrote viewer JSON: %s (%d papers)", viewer_path, len(viewer_papers))

    # Also write HTML
    html = format_digest_html([{"paper": p} for p in viewer_papers], datetime.now().strftime("%Y-%m-%d"))
    html_path = REPORTS_DIR.parent.parent / f"manual-journal-digest-{datetime.now().strftime('%Y-%m-%d')}.html"
    html_path.write_text(html, encoding="utf-8")
    LOG.info("Wrote HTML: %s", html_path)

    # Print top 20
    print(f"\n{'='*60}")
    print(f"Manual Journal Digest — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Total papers: {len(viewer_papers)}")
    print(f"{'='*60}\n")
    for i, p in enumerate(viewer_papers[:20], 1):
        score = p.get("relevance", 0)
        stars = "★" * int(score * 5)
        print(f"[{i:02d}] {stars} ({score:.2f}) {p['title']}")
        print(f"      {p['authors'][0] if p.get('authors') else '?'} · {p['venue']} · {p.get('published_at','')}")
        print()

if __name__ == "__main__":
    main()
