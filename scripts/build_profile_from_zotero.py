#!/usr/bin/env python3
"""
Build research-interest.json from Zotero library statistics.
Fetches only top-N items directly from API (no zot.everything() pagination),
extracts top tags/title-terms/venues, then uses an LLM to generate interests.
"""
import argparse
import json
import logging
import re
import sys
import time
from collections import Counter
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
LOG = logging.getLogger(__name__)

STOPWORDS = {
    "about", "across", "analysis", "approach", "based", "data", "effect",
    "effects", "evidence", "from", "impact", "impacts", "into", "model",
    "models", "method", "methods", "paper", "study", "studies", "system",
    "using", "with", "evidence", "policy", "policies", "new", "can", "may",
}


def _fetch_top_items(library_id: int, api_key: str, library_type: str, limit: int, delay: float):
    import httpx
    headers = {
        "Zotero-API-Key": api_key,
        "Zotero-API-Version": "3",
    }
    url = f"https://api.zotero.org/{library_type}s/{library_id}/items/top?limit={limit}&format=json"
    resp = httpx.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _extract_terms(title: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", title)
    return [t.lower() for t in tokens if t.lower() not in STOPWORDS]


def _summarize(items: list[dict]) -> dict:
    tag_counter = Counter()
    term_counter = Counter()
    venue_counter = Counter()
    year_counter = Counter()

    for item in items:
        data = item.get("data", {})
        # tags
        for t in data.get("tags", []):
            tag_val = t.get("tag", "")
            if tag_val:
                tag_counter[tag_val.lower()] += 1
        # title terms
        for term in _extract_terms(data.get("title", "") or ""):
            term_counter[term] += 1
        # venue
        venue = (data.get("publicationTitle") or "").strip()
        if venue:
            venue_counter[venue] += 1
        # year
        year = (data.get("date", "") or "")[:4]
        if year.isdigit():
            year_counter[year] += 1

    return {
        "top_tags": [t for t, c in tag_counter.most_common(20)],
        "top_terms": [t for t, c in term_counter.most_common(30)],
        "top_venues": [v for v, c in venue_counter.most_common(10)],
        "top_years": [y for y, c in year_counter.most_common(5)],
        "item_count": len(items),
    }


def _call_llm(summarize_result: dict, api_key: str) -> dict:
    """Call local LLM to generate research-interest.json from statistics."""
    prompt = f"""You are helping a researcher generate their research-interest.json profile based on their Zotero library statistics.

Statistics from their Zotero library ({summarize_result['item_count']} top-level items):

Top tags: {', '.join(summarize_result['top_tags'])}
Top title terms: {', '.join(summarize_result['top_terms'])}
Top venues: {', '.join(summarize_result['top_venues'])}
Top years: {', '.join(summarize_result['top_years'])}

Generate a research-interest.json with 3-6 interest areas. Each interest needs:
- interest_id (kebab-case)
- label (Chinese)
- query_aliases (3-5 English keyword phrases)
- method_keywords (2-3 methodological keywords like DID, RD, IV, etc.)
- categories (1-3 arXiv categories relevant to the field)

Return ONLY valid JSON (no markdown, no explanation):
{{
  "interests": [
    {{
      "interest_id": "...",
      "label": "...",
      "enabled": true,
      "categories": [...],
      "method_keywords": [...],
      "query_aliases": [...]
    }}
  ]
}}
"""
    import httpx
    resp = httpx.post(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "qwen-plus",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    # strip markdown code fences
    content = re.sub(r"```json\\?","", content)
    content = re.sub(r"```","", content)
    return json.loads(content.strip())


def main():
    parser = argparse.ArgumentParser(description="Build research-interest.json from Zotero library")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--limit", type=int, default=100, help="Number of top items to analyze")
    parser.add_argument("--output", default=None, help="Output path (default: profiles/research-interest.json)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent.parent))
    import httpx

    # Load config
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)

    zotero_cfg = cfg.get("zotero", {})
    semantic_cfg = cfg.get("semantic_search", {})
    library_id = zotero_cfg["library_id"]
    api_key = zotero_cfg["api_key"]
    library_type = zotero_cfg.get("library_type", "user")
    embedding_api_key = semantic_cfg.get("embedding_config", {}).get("api_key", "")

    # Step 1: fetch top items directly
    LOG.info(f"Fetching top {args.limit} items from Zotero...")
    t0 = time.time()
    items = _fetch_top_items(library_id, api_key, library_type, args.limit, delay=0.2)
    LOG.info(f"Fetched {len(items)} items in {time.time()-t0:.1f}s")

    # Step 2: summarize
    summary = _summarize(items)
    LOG.info(f"Top tags: {summary['top_tags'][:10]}")
    LOG.info(f"Top terms: {summary['top_terms'][:10]}")

    # Step 3: LLM generates interests
    LOG.info("Generating interests via LLM...")
    interests = _call_llm(summary, embedding_api_key)

    # Step 4: build full profile
    profile = {
        "schema_version": "1.1.0",
        "profile_id": "cae-research-interest",
        "profile_name": "中央财经大学研究兴趣",
        "updated_at": "2026-04-27T14:40:00+08:00",
        "maintainer": "hermes-agent",
        "zotero_basis": {
            "collections": [],
            "tags": summary["top_tags"],
            "notes": f"范翻研究方向，基于 Zotero {summary['item_count']} 篇文献的 tag/title terms 分析自动生成"
        },
        "retrieval_defaults": {
            "logic": "OR",
            "sort_by": "lastUpdatedDate",
            "sort_order": "descending",
            "since_days": 7,
            "max_results_per_interest": 10,
            "max_pages": 10,
        },
        "interests": interests.get("interests", []),
    }

    output_path = Path(args.output) if args.output else Path(__file__).parent.parent / "profiles" / "research-interest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        output_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        LOG.info(f"Written to {output_path}")

    print(f"\n✅ Generated {len(profile['interests'])} interests:")
    for interest in profile["interests"]:
        print(f"  - [{interest['interest_id']}] {interest['label']}")


if __name__ == "__main__":
    main()
