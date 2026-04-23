"""OpenAlex pipeline CLI."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codex_research_assist.openalex_pipeline import (
    NBER_PROGRAM_KEYWORDS,
    incremental_sync,
    parse_paper,
    run_search,
    search_and_parse,
)


def cmd_search(args):
    """Run keyword/program search."""
    papers = search_and_parse(
        keywords=args.keywords.split(",") if args.keywords else None,
        program=args.program,
        from_date=args.from_date,
        to_date=args.to_date,
        per_page=args.limit,
    )

    print(f"Found {len(papers)} papers:\n")

    for i, p in enumerate(papers, 1):
        title = p["title"][:70]
        nber_id = p["nber_id"] or "N/A"
        cited = p["cited_by_count"]
        date = p["publication_date"]

        print(f"{i}. {title}...")
        print(f"   NBER: {nber_id} | Date: {date} | Cited: {cited}")
        print()


def cmd_interests(args):
    """Search multiple interests from JSON config."""
    config_path = Path(args.config).expanduser()

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    interests = config.get("interests", [])

    if not interests:
        print("No interests found in config")
        sys.exit(1)

    result = run_search(interests, per_interest_limit=args.limit)

    print(f"\n=== Results ===")
    print(f"Total papers: {result['total']}\n")

    for name, papers in result["interests"].items():
        print(f"## {name}: {len(papers)} papers")

        for p in papers:
            title = p["title"][:60]
            print(f"  - {title}...")

        print()


def cmd_sync(args):
    """Run incremental sync."""
    result = incremental_sync(days_back=args.days)

    print(f"=== Incremental Sync ===")
    print(f"Period: {result['from_date']} to {result['to_date']}")
    print(f"New papers: {result['new_papers']}")
    print(f"Total cached: {result['total_cached']}")


def cmd_programs(args):
    """List all program keyword mappings."""
    print("=== NBER Program Keywords Mapping ===\n")

    for code, keywords in sorted(NBER_PROGRAM_KEYWORDS.items()):
        print(f"{code}: {', '.join(keywords)}")


def main():
    parser = argparse.ArgumentParser(description="OpenAlex NBER Pipeline")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # search command
    search_parser = subparsers.add_parser("search", help="Search NBER papers")
    search_parser.add_argument("--keywords", "-k", help="Comma-separated keywords")
    search_parser.add_argument("--program", "-p", help="NBER program code (e.g., CN, PE)")
    search_parser.add_argument("--from-date", help="Start date (YYYY-MM-DD)")
    search_parser.add_argument("--to-date", help="End date (YYYY-MM-DD)")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    search_parser.set_defaults(func=cmd_search)

    # interests command
    interests_parser = subparsers.add_parser("interests", help="Search from interests config")
    interests_parser.add_argument("config", help="Path to interests JSON config")
    interests_parser.add_argument("--limit", "-l", type=int, default=10, help="Max per interest")
    interests_parser.set_defaults(func=cmd_interests)

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Incremental sync")
    sync_parser.add_argument("--days", "-d", type=int, default=30, help="Days to look back")
    sync_parser.set_defaults(func=cmd_sync)

    # programs command
    programs_parser = subparsers.add_parser("programs", help="List program keywords")
    programs_parser.set_defaults(func=cmd_programs)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
