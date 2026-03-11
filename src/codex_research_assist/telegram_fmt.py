"""Telegram message formatting for research-assist digest.

Formats candidates as Telegram-compatible Markdown messages.
Does NOT send — the caller (agent or script) handles delivery.
"""
from __future__ import annotations


def _escape_md(text: str) -> str:
    """Escape Telegram MarkdownV1 special characters."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def format_paper_card(idx: int, candidate: dict) -> str:
    """Format a single candidate as a Telegram paper card."""
    paper = candidate.get("paper", {})
    triage = candidate.get("triage", {})
    scores = candidate.get("_scores", {})

    title = paper.get("title", "Untitled")
    authors = paper.get("authors", [])
    arxiv_id = paper.get("identifiers", {}).get("arxiv_id", "")
    url = paper.get("identifiers", {}).get("url", "")
    abstract = paper.get("abstract", "")
    matched = triage.get("matched_interest_labels", [])

    # Author line
    if len(authors) > 2:
        author_str = f"{authors[0]} et al."
    elif len(authors) == 2:
        author_str = f"{authors[0]} & {authors[1]}"
    elif authors:
        author_str = authors[0]
    else:
        author_str = ""

    lines = []

    # Title with link
    if url:
        lines.append(f"*{idx}.* [{_escape_md(title)}]({url})")
    else:
        lines.append(f"*{idx}. {_escape_md(title)}*")

    # Author
    if author_str:
        lines.append(f"    {_escape_md(author_str)}")

    # Tags
    if matched:
        tags = " ".join(f"#{t.replace(' ', '-')}" for t in matched[:3])
        lines.append(f"    {tags}")

    # Score
    if scores:
        lines.append(f"    📊 Score: {scores.get('total', 0):.2f}")

    # Abstract snippet
    if abstract:
        snippet = abstract[:120] + "…" if len(abstract) > 120 else abstract
        lines.append(f"    💡 {_escape_md(snippet)}")

    return "\n".join(lines)


def format_digest_telegram(candidates: list[dict], date_str: str) -> str:
    """Format full digest as a Telegram push message."""
    header = f"📬 *Research Digest | {date_str} | {len(candidates)} papers*"
    separator = "━━━━━━━━━━━━━━━━━━━━"

    if not candidates:
        return f"{header}\n\nNo new papers found."

    cards = [format_paper_card(i, c) for i, c in enumerate(candidates, 1)]

    parts = [header, separator, ""]
    parts.extend(c + "\n" for c in cards)
    parts.append(separator)

    return "\n".join(parts)


def format_search_telegram(papers: list[dict], query: str) -> str:
    """Format ad-hoc search results as a Telegram message."""
    header = f"🔍 *Search: \"{_escape_md(query)}\" | {len(papers)} results*"

    if not papers:
        return f"{header}\n\nNo results found."

    lines = [header, ""]
    for i, p in enumerate(papers, 1):
        title = p.get("title", "Untitled")
        url = p.get("html_url", "")
        authors = p.get("authors", [])
        author_str = authors[0] + " et al." if len(authors) > 2 else ", ".join(authors) if authors else ""
        summary = (p.get("summary") or "")[:100]

        if url:
            lines.append(f"*{i}.* [{_escape_md(title)}]({url})")
        else:
            lines.append(f"*{i}. {_escape_md(title)}*")
        if author_str:
            lines.append(f"    {_escape_md(author_str)}")
        if summary:
            lines.append(f"    💡 {_escape_md(summary)}")
        lines.append("")

    return "\n".join(lines)
