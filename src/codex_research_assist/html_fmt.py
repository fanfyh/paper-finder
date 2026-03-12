"""HTML digest generator for research-assist."""

import html


def format_digest_html(candidates: list[dict], date_str: str) -> str:
    """Generate a self-contained HTML digest page for mobile viewing."""
    paper_count = len(candidates)

    # Generate paper cards
    cards_html = []
    for idx, candidate in enumerate(candidates, 1):
        paper = candidate["paper"]
        triage = candidate.get("triage", {})
        scores = candidate.get("_scores", {})

        title = html.escape(paper["title"])
        authors = paper.get("authors", [])
        author_line = html.escape(authors[0] + " et al." if len(authors) > 2 else ", ".join(authors[:2]))
        abstract = html.escape(paper["abstract"])
        arxiv_id = paper["identifiers"].get("arxiv_id", "")
        url = paper["identifiers"].get("url", "")

        # Score breakdown
        total = scores.get("total", 0)
        rel = scores.get("relevance", 0)
        rec = scores.get("recency", 0)
        nov = scores.get("novelty", 0)
        score_class = "high" if total >= 0.7 else "medium" if total >= 0.5 else "low"

        # Interest tags
        tags = triage.get("matched_interest_labels", [])
        tags_html = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in tags)

        card = f"""
        <div class="paper-card">
            <div class="paper-header">
                <span class="paper-number">#{idx}</span>
                <span class="score-badge {score_class}">{total:.2f} (R:{rel:.2f} T:{rec:.2f} N:{nov:.2f})</span>
            </div>
            <h2><a href="{html.escape(url)}" target="_blank">{title}</a></h2>
            <p class="authors">{author_line}</p>
            <p class="arxiv-id">arXiv: {html.escape(arxiv_id)}</p>
            <div class="tags">{tags_html}</div>
            <details>
                <summary>Abstract (tap to expand)</summary>
                <p class="abstract">{abstract}</p>
            </details>
        </div>
        """
        cards_html.append(card)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Digest - {html.escape(date_str)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            line-height: 1.6;
            padding: 16px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid #0f3460;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header p {{ color: #a0a0a0; font-size: 14px; }}
        .paper-card {{
            background: #16213e;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .paper-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .paper-number {{
            font-weight: bold;
            color: #53a8b6;
            font-size: 14px;
        }}
        .score-badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .score-badge.high {{ background: #2d5016; color: #90ee90; }}
        .score-badge.medium {{ background: #5a4a1a; color: #ffd700; }}
        .score-badge.low {{ background: #3a3a3a; color: #a0a0a0; }}
        h2 {{
            font-size: 18px;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        h2 a {{
            color: #53a8b6;
            text-decoration: none;
        }}
        h2 a:hover {{ text-decoration: underline; }}
        .authors {{
            color: #a0a0a0;
            font-size: 14px;
            margin-bottom: 4px;
        }}
        .arxiv-id {{
            color: #808080;
            font-size: 13px;
            margin-bottom: 8px;
        }}
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
        }}
        .tag {{
            background: #0f3460;
            color: #53a8b6;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
        }}
        details {{
            margin-top: 12px;
        }}
        summary {{
            cursor: pointer;
            color: #53a8b6;
            font-weight: 500;
            padding: 8px 0;
            user-select: none;
        }}
        summary:hover {{ color: #6bc4d4; }}
        .abstract {{
            margin-top: 8px;
            padding: 12px;
            background: #0f1419;
            border-radius: 4px;
            font-size: 14px;
            line-height: 1.7;
        }}
        .footer {{
            text-align: center;
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #0f3460;
            color: #808080;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Research Digest</h1>
        <p>{html.escape(date_str)} • {paper_count} papers</p>
    </div>
    {''.join(cards_html)}
    <div class="footer">
        Generated by research-assist
    </div>
</body>
</html>"""


def format_search_html(papers: list[dict], query: str) -> str:
    """Generate HTML page for ad-hoc search results."""
    paper_count = len(papers)

    cards_html = []
    for idx, paper in enumerate(papers, 1):
        title = html.escape(paper.get("title", "Untitled"))
        authors = paper.get("authors", [])
        author_line = html.escape(authors[0] + " et al." if len(authors) > 2 else ", ".join(authors[:2]))
        summary = html.escape(paper.get("summary", ""))
        url = html.escape(paper.get("html_url", ""))
        arxiv_id = html.escape(paper.get("arxiv_id", ""))

        card = f"""
        <div class="paper-card">
            <div class="paper-header">
                <span class="paper-number">#{idx}</span>
            </div>
            <h2><a href="{url}" target="_blank">{title}</a></h2>
            <p class="authors">{author_line}</p>
            <p class="arxiv-id">arXiv: {arxiv_id}</p>
            <details>
                <summary>Abstract (tap to expand)</summary>
                <p class="abstract">{summary}</p>
            </details>
        </div>
        """
        cards_html.append(card)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search Results - {html.escape(query)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            line-height: 1.6;
            padding: 16px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid #0f3460;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header p {{ color: #a0a0a0; font-size: 14px; }}
        .paper-card {{
            background: #16213e;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .paper-header {{
            margin-bottom: 12px;
        }}
        .paper-number {{
            font-weight: bold;
            color: #53a8b6;
            font-size: 14px;
        }}
        h2 {{
            font-size: 18px;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        h2 a {{
            color: #53a8b6;
            text-decoration: none;
        }}
        h2 a:hover {{ text-decoration: underline; }}
        .authors {{
            color: #a0a0a0;
            font-size: 14px;
            margin-bottom: 4px;
        }}
        .arxiv-id {{
            color: #808080;
            font-size: 13px;
            margin-bottom: 12px;
        }}
        details {{
            margin-top: 12px;
        }}
        summary {{
            cursor: pointer;
            color: #53a8b6;
            font-weight: 500;
            padding: 8px 0;
            user-select: none;
        }}
        summary:hover {{ color: #6bc4d4; }}
        .abstract {{
            margin-top: 8px;
            padding: 12px;
            background: #0f1419;
            border-radius: 4px;
            font-size: 14px;
            line-height: 1.7;
        }}
        .footer {{
            text-align: center;
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #0f3460;
            color: #808080;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Search Results</h1>
        <p>Query: {html.escape(query)} • {paper_count} papers</p>
    </div>
    {''.join(cards_html)}
    <div class="footer">
        Generated by research-assist
    </div>
</body>
</html>"""
