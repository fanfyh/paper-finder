"""Telegram message formatting for research-assist digest.

Formats candidates as Telegram HTML messages (parse_mode='HTML').
Does NOT send — the caller (agent or script) handles delivery.
"""
from __future__ import annotations
import html


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse_mode."""
    return html.escape(text)


def format_digest_telegram(candidates: list[dict], date_str: str) -> str:
    """Format digest as a compact Top 5 Telegram HTML message.

    Returns a single string in Telegram HTML format showing only the top 5 papers.
    Full content with abstracts should be sent as a separate HTML attachment.
    """
    total = len(candidates)
    header = f"📬 <b>Research Digest | {_escape_html(date_str)} | {total} papers</b>"

    if not candidates:
        return f"{header}\n\nNo new papers found."

    lines = [header, ""]

    # Show only top 5
    top_candidates = candidates[:5]
    for i, candidate in enumerate(top_candidates, 1):
        paper = candidate.get("paper", {})
        scores = candidate.get("_scores", {})

        title = paper.get("title", "Untitled")
        authors = paper.get("authors", [])
        url = paper.get("identifiers", {}).get("url", "")

        # Author line
        if len(authors) > 2:
            author_str = f"{authors[0]} et al."
        elif len(authors) == 2:
            author_str = f"{authors[0]} & {authors[1]}"
        elif authors:
            author_str = authors[0]
        else:
            author_str = ""

        # Title with link
        if url:
            lines.append(f"{i}. <a href=\"{_escape_html(url)}\">{_escape_html(title)}</a>")
        else:
            lines.append(f"{i}. {_escape_html(title)}")

        # Author and score on same line
        info_parts = []
        if author_str:
            info_parts.append(_escape_html(author_str))
        if scores:
            info_parts.append(f"📊 {scores.get('total', 0):.2f}")

        if info_parts:
            lines.append(f"   {' · '.join(info_parts)}")

        lines.append("")

    # Footer if more than 5 papers
    if total > 5:
        lines.append("📎 Full digest with abstracts attached below")

    return "\n".join(lines)


def format_search_telegram(papers: list[dict], query: str) -> str:
    """Format ad-hoc search results as a compact Telegram HTML message."""
    total = len(papers)
    header = f"🔍 <b>Search: \"{_escape_html(query)}\" | {total} results</b>"

    if not papers:
        return f"{header}\n\nNo results found."

    lines = [header, ""]

    # Show up to 5 results
    for i, p in enumerate(papers[:5], 1):
        title = p.get("title", "Untitled")
        url = p.get("html_url", "")
        authors = p.get("authors", [])

        # Author line
        if len(authors) > 2:
            author_str = f"{authors[0]} et al."
        elif authors:
            author_str = ", ".join(authors)
        else:
            author_str = ""

        # Title with link
        if url:
            lines.append(f"{i}. <a href=\"{_escape_html(url)}\">{_escape_html(title)}</a>")
        else:
            lines.append(f"{i}. {_escape_html(title)}")

        # Author
        if author_str:
            lines.append(f"   {_escape_html(author_str)}")

        lines.append("")

    if total > 5:
        lines.append(f"<i>Showing top 5 of {total} results</i>")

    return "\n".join(lines)
