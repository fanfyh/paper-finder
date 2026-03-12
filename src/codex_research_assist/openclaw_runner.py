#!/usr/bin/env python3
"""OpenClaw skill CLI entry point for codex-research-assist.

No FastMCP dependency — pure CLI that outputs markdown to stdout.

Usage:
    python3 -m codex_research_assist.openclaw_runner --action digest --config ~/.openclaw/skills/research-assist/config.json
    python3 -m codex_research_assist.openclaw_runner --action search --query "gaussian process" --top 5
    python3 -m codex_research_assist.openclaw_runner --action profile-refresh --config ~/.openclaw/skills/research-assist/config.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .arxiv_profile_pipeline.client import fetch_arxiv_feed
from .arxiv_profile_pipeline.parser import parse_feed
from .arxiv_profile_pipeline.pipeline import run_pipeline
from .arxiv_profile_pipeline.query import build_search_query
from .controller.profile_refresh_policy import evaluate_profile_refresh_policy
from .ranker import rank_candidates
from .telegram_fmt import format_digest_telegram, format_search_telegram
from .html_fmt import format_digest_html, format_search_html
from .telegram_sender import send_digest, send_message

LOG = logging.getLogger("openclaw_runner")

DEFAULT_CONFIG_DIR = Path.home() / ".openclaw" / "skills" / "research-assist"
DEFAULT_CONFIG = DEFAULT_CONFIG_DIR / "config.json"


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def expand_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def get_profile_path(config: dict) -> Path:
    profile_path_str = config.get("profile_path", "~/.openclaw/skills/research-assist/profiles/research-interest.json")
    return expand_path(profile_path_str)


def get_output_root(config: dict) -> Path:
    output_root_str = config.get("output_root", "~/.openclaw/skills/research-assist/reports")
    return expand_path(output_root_str)


def _toml_quote(value: str) -> str:
    """Escape a string for TOML double-quoted value."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def create_temp_toml_config(config: dict, profile_path: Path, output_root: Path) -> Path:
    """Write a minimal TOML config consumed by run_pipeline / evaluate_profile_refresh_policy."""
    retrieval_defaults = config.get("retrieval_defaults", {})
    max_age_days = retrieval_defaults.get("max_age_days", 7)

    toml_text = "\n".join([
        f"profile_path = {_toml_quote(profile_path.as_posix())}",
        f"output_root = {_toml_quote(output_root.as_posix())}",
        "",
        "[artifacts]",
        "write_candidate_markdown = false",
        "",
        "[controller]",
        'mode = "internal-staged"',
        "",
        "[controller.profile_refresh]",
        "enabled = true",
        f"max_age_days = {int(max_age_days)}",
        "refresh_if_missing = true",
        "",
    ])

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", encoding="utf-8", delete=False)
    temp_file.write(toml_text)
    temp_file.close()
    return Path(temp_file.name)


def format_digest_markdown(digest_json_path: Path, candidates: list[dict]) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# arXiv Research Digest {date_str}", ""]

    if not candidates:
        lines.append("No new papers found matching your research interests.")
        return "\n".join(lines)

    lines.append(f"Found {len(candidates)} new papers:")
    lines.append("")

    for i, candidate in enumerate(candidates, 1):
        paper = candidate.get("paper", {})
        triage = candidate.get("triage", {})
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", [])
        arxiv_id = paper.get("identifiers", {}).get("arxiv_id", "")
        url = paper.get("identifiers", {}).get("url", "")
        abstract = paper.get("abstract", "")
        matched_interests = triage.get("matched_interest_labels", [])

        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        lines.append(f"## {i}. {title}")
        if author_str:
            lines.append(f"**Authors:** {author_str}")
        if arxiv_id:
            lines.append(f"**arXiv ID:** {arxiv_id}")
        if url:
            lines.append(f"**URL:** {url}")
        if matched_interests:
            lines.append(f"**Matched Interests:** {', '.join(matched_interests)}")
        scores = candidate.get("_scores")
        if scores:
            lines.append(f"**Score:** {scores['total']:.2f} (rel={scores['relevance']:.2f} rec={scores['recency']:.2f} nov={scores['novelty']:.2f})")
        if abstract:
            abstract_preview = abstract[:300] + ("..." if len(abstract) > 300 else "")
            lines.append(f"\n**Abstract:** {abstract_preview}")
        lines.append("")

    lines.append("---")
    lines.append(f"Full digest: {digest_json_path.as_posix()}")
    return "\n".join(lines)


def format_search_markdown(papers: list[dict], query: str) -> str:
    lines = [f"# arXiv Search: \"{query}\"", ""]

    if not papers:
        lines.append("No results found.")
        return "\n".join(lines)

    lines.append(f"Found {len(papers)} results:")
    lines.append("")

    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", [])
        arxiv_id = paper.get("arxiv_id", "")
        url = paper.get("html_url", "")
        abstract = paper.get("summary", "")

        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        lines.append(f"## {i}. {title}")
        if author_str:
            lines.append(f"**Authors:** {author_str}")
        if arxiv_id:
            lines.append(f"**arXiv ID:** {arxiv_id}")
        if url:
            lines.append(f"**URL:** {url}")
        if abstract:
            abstract_preview = abstract[:250] + ("..." if len(abstract) > 250 else "")
            lines.append(f"\n**Abstract:** {abstract_preview}")
        lines.append("")

    return "\n".join(lines)


def format_profile_refresh_markdown(policy_result: dict) -> str:
    lines = ["# Profile Refresh Status", ""]
    profile_path = policy_result.get("profile_path", "")
    profile_exists = policy_result.get("profile_exists", False)
    profile_age_days = policy_result.get("profile_age_days")
    refresh_info = policy_result.get("controller", {}).get("profile_refresh", {})
    required = refresh_info.get("required", False)
    reason = refresh_info.get("reason", "unknown")

    lines.append(f"**Profile Path:** {profile_path}")
    lines.append(f"**Profile Exists:** {profile_exists}")
    if profile_age_days is not None:
        lines.append(f"**Profile Age:** {profile_age_days:.1f} days")
    lines.append(f"**Refresh Required:** {required}")
    lines.append(f"**Reason:** {reason}")
    lines.append("")
    if required:
        lines.append("The profile needs to be refreshed.")
        lines.append("")
        lines.append("Run `bash scripts/profile/refresh_profile.sh --config automation/arxiv-profile-digest.example.toml` to regenerate the live profile.")
    else:
        lines.append("The profile is up to date.")
    return "\n".join(lines)


def action_digest(config: dict, fmt: str = "markdown") -> str:
    profile_path = get_profile_path(config)
    output_root = get_output_root(config)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    temp_toml_path = create_temp_toml_config(config, profile_path, output_root)

    try:
        LOG.info("Checking profile refresh policy...")
        policy_result = evaluate_profile_refresh_policy(config_path=temp_toml_path, profile_override=None)
        refresh_required = policy_result.get("controller", {}).get("profile_refresh", {}).get("required", False)
        if refresh_required:
            reason = policy_result.get("controller", {}).get("profile_refresh", {}).get("reason", "unknown")
            LOG.warning("Profile refresh required: %s", reason)
            LOG.warning("Proceeding with retrieval using existing profile (if available)")

        LOG.info("Running arXiv retrieval pipeline...")
        result = run_pipeline(config_path=temp_toml_path, profile_path=profile_path, write_candidate_markdown_override=False)
        digest_json_path = Path(result["digest_json_path"])
        candidate_count = result["candidate_count"]
        LOG.info("Retrieved %d candidates", candidate_count)

        digest_data = json.loads(digest_json_path.read_text(encoding="utf-8"))
        candidate_paths = digest_data.get("candidate_paths", [])
        candidates = []
        for candidate_path in candidate_paths:
            try:
                candidate_data = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
                candidates.append(candidate_data)
            except Exception as exc:
                LOG.warning("Failed to load candidate %s: %s", candidate_path, exc)

        # Rank candidates using the profile
        if candidates and profile_path.exists():
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            # Load seen IDs from the same state path the pipeline uses
            profile_defaults = profile.get("retrieval_defaults", {})
            state_path_str = profile_defaults.get("state_path", ".state/arxiv_profile_seen.json")
            state_path = Path(state_path_str)
            if not state_path.is_absolute():
                state_path = Path.cwd() / state_path
            history_ids: set[str] = set()
            if state_path.exists():
                try:
                    seen_data = json.loads(state_path.read_text(encoding="utf-8"))
                    history_ids = set(seen_data.get("ids", []))
                except Exception:
                    pass
            candidates = rank_candidates(candidates, profile, history_ids)
            LOG.info("Ranked %d candidates", len(candidates))

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Write HTML file for browser viewing
        html_content = format_digest_html(candidates, date_str)
        html_path = output_root / f"digest-{date_str}.html"
        html_path.write_text(html_content, encoding="utf-8")
        LOG.info("Wrote HTML digest to %s", html_path)

        if fmt == "telegram":
            # Generate compact Telegram summary
            telegram_summary = format_digest_telegram(candidates, date_str)

            # Write telegram.json metadata
            telegram_json_path = output_root / f"digest-{date_str}.telegram.json"
            telegram_json_data = {
                "summary": telegram_summary,
                "html_path": html_path.as_posix(),
                "total_papers": len(candidates)
            }
            telegram_json_path.write_text(json.dumps(telegram_json_data, indent=2, ensure_ascii=False), encoding="utf-8")
            LOG.info("Wrote Telegram metadata to %s", telegram_json_path)

            # Try to send via Telegram
            send_status = "skipped — TELEGRAM_BOT_TOKEN not set"
            try:
                send_digest(telegram_summary, html_path)
                send_status = "sent ✓"
            except Exception as exc:
                LOG.warning("Failed to send to Telegram: %s", exc)
                send_status = f"failed — {exc}"

            # Compact stdout output
            lines = [f"Found {len(candidates)} papers, top 5:"]
            for i, candidate in enumerate(candidates[:5], 1):
                paper = candidate.get("paper", {})
                title = paper.get("title", "Untitled")
                arxiv_id = paper.get("identifiers", {}).get("arxiv_id", "")
                scores = candidate.get("_scores", {})
                score = scores.get("total", 0.0)
                lines.append(f"{i}. [{score:.2f}] {title[:60]}... ({arxiv_id})")
            lines.append(f"Files: {html_path.name}, {telegram_json_path.name}")
            lines.append(f"Telegram: {send_status}")
            return "\n".join(lines)

        # Default markdown output to stdout
        return format_digest_markdown(digest_json_path, candidates)
    finally:
        try:
            temp_toml_path.unlink()
        except Exception:
            pass


def action_search(query: str, top: int = 5, fmt: str = "markdown") -> str:
    LOG.info("Searching arXiv for: %s", query)
    search_query = build_search_query(categories=[], keywords=[query], exclude_keywords=None, logic="OR")
    xml_text = fetch_arxiv_feed(search_query, start=0, max_results=top, sort_by="relevance", sort_order="descending")
    papers = parse_feed(xml_text)
    LOG.info("Found %d results", len(papers))

    papers_subset = papers[:top]

    if fmt == "telegram":
        # Generate compact Telegram summary
        telegram_summary = format_search_telegram(papers_subset, query)

        # Generate HTML for browser viewing
        html_content = format_search_html(papers_subset, query)

        # Write files to a search output directory
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        search_output_dir = Path.home() / ".openclaw" / "skills" / "research-assist" / "reports" / "search"
        search_output_dir.mkdir(parents=True, exist_ok=True)

        html_path = search_output_dir / f"search-{date_str}.html"
        html_path.write_text(html_content, encoding="utf-8")
        LOG.info("Wrote HTML search results to %s", html_path)

        telegram_json_path = search_output_dir / f"search-{date_str}.telegram.json"
        telegram_json_data = {
            "summary": telegram_summary,
            "html_path": html_path.as_posix(),
            "query": query,
            "total_results": len(papers_subset)
        }
        telegram_json_path.write_text(json.dumps(telegram_json_data, indent=2, ensure_ascii=False), encoding="utf-8")
        LOG.info("Wrote Telegram metadata to %s", telegram_json_path)

        # Try to send via Telegram (summary + HTML attachment)
        send_status = "skipped — TELEGRAM_BOT_TOKEN not set"
        try:
            send_digest(telegram_summary, html_path)
            send_status = "sent ✓"
        except Exception as exc:
            LOG.warning("Failed to send to Telegram: %s", exc)
            send_status = f"failed — {exc}"

        # Compact stdout output
        lines = [f"Found {len(papers_subset)} results for \"{query}\":"]
        for i, paper in enumerate(papers_subset, 1):
            title = paper.get("title", "Untitled")
            arxiv_id = paper.get("arxiv_id", "")
            lines.append(f"{i}. {title[:60]}... ({arxiv_id})")
        lines.append(f"Files: {html_path.name}, {telegram_json_path.name}")
        lines.append(f"Telegram: {send_status}")
        return "\n".join(lines)

    return format_search_markdown(papers_subset, query)


def action_profile_refresh(config: dict) -> str:
    profile_path = get_profile_path(config)
    output_root = get_output_root(config)
    temp_toml_path = create_temp_toml_config(config, profile_path, output_root)

    try:
        LOG.info("Evaluating profile refresh policy...")
        policy_result = evaluate_profile_refresh_policy(config_path=temp_toml_path, profile_override=None)
        return format_profile_refresh_markdown(policy_result)
    finally:
        try:
            temp_toml_path.unlink()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Codex Research Assist OpenClaw Runner")
    parser.add_argument("--action", required=True, choices=["digest", "search", "profile-refresh"], help="Action to perform")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config.json")
    parser.add_argument("--query", type=str, default="", help="Search query (for search action)")
    parser.add_argument("--top", type=int, default=5, help="Number of results (for search action)")
    parser.add_argument("--format", choices=["markdown", "telegram"], default="markdown", help="Output format (default: markdown)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(name)s %(levelname)s: %(message)s", stream=sys.stderr)

    try:
        if args.action == "digest":
            config = load_config(args.config)
            output = action_digest(config, fmt=args.format)
        elif args.action == "search":
            if not args.query:
                parser.error("--query required for search action")
            output = action_search(args.query, args.top, fmt=args.format)
        elif args.action == "profile-refresh":
            config = load_config(args.config)
            output = action_profile_refresh(config)
        else:
            parser.error(f"Unknown action: {args.action}")
        print(output)
    except Exception as exc:
        LOG.error("Error: %s", exc, exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
