"""OpenAlex API unified client for paper-finder.

Single entry point for all search operations — journals and working-paper
institutions — driven by two asset files:

  - journal_list.json              → journal source aliases (source IDs, S-prefixed)
  - working_paper_sources.json     → working-paper institution aliases (IDs, I-prefixed)
                                      plus SSRN source ID

No hardcoded IDs. All resolution goes through resolve_source().
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import os

import requests

OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_BASE_URL = os.getenv("OPENALEX_BASE_URL", "https://api.openalex.org")
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "paper-finder@example.com")

log = logging.getLogger(__name__)

# ── Asset paths ────────────────────────────────────────────────────────────────

# Assets live at: /home/agentuser/.claude/tools/paper-finder/assets/
# client.py is at: .../codex_research_assist/client.py
# So: client.py → codex_research_assist → src → project_root
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ASSETS = _PROJECT_ROOT / "assets"
JOURNAL_LIST_PATH = _ASSETS / "journal_list.json"
WP_SOURCES_PATH = _ASSETS / "working_paper_sources.json"

# ── Global caches (lazy, cleared between test runs via module-level hack) ─────

_journal_aliases: dict[str, str] | None = None  # e.g. "JPE" → "S18284184"
_wp_institutions: dict[str, str] | None = None  # e.g. "NBER" → "I1321305853"
_wp_ssrn_source: str | None = None  # e.g. "S4210172589"


# ── Loading helpers ────────────────────────────────────────────────────────────

def _load_journal_aliases() -> dict[str, str]:
    """Load journal aliases from journal_list.json.

    Each entry has ``title`` and ``openalex_id``.  We generate an abbreviation
    (via _title_to_alias) as the primary key and also store its uppercase
    variant for case-insensitive lookup.

    Returns:
        Mapping from uppercase alias to OpenAlex source ID (S-prefixed).
    """
    global _journal_aliases
    if _journal_aliases is not None:
        return _journal_aliases

    aliases: dict[str, str] = {}
    try:
        entries = json.loads(JOURNAL_LIST_PATH.read_text())
    except Exception as exc:
        log.warning("Could not load journal_list.json: %s", exc)
        _journal_aliases = {}
        return _journal_aliases

    for entry in entries:
        title = entry.get("title", "")
        openalex_id = entry.get("openalex_id", "")
        if not title or not openalex_id:
            log.warning("Skipping journal entry with missing title or openalex_id: %s", entry)
            continue
        alias = _title_to_alias(title)
        if alias:
            if alias in aliases or alias.upper() in aliases:
                log.warning(
                    "Alias collision for '%s' -> '%s' (OpenAlex: %s). "
                    "Another journal already registered this alias.",
                    title, alias, openalex_id,
                )
            aliases[alias] = openalex_id
            aliases[alias.upper()] = openalex_id

    log.info("Loaded %d journal aliases from %s", len(aliases), JOURNAL_LIST_PATH)
    _journal_aliases = aliases
    return _journal_aliases


def _load_wp_institutions() -> dict[str, str]:
    """Load working-paper institution aliases from working_paper_sources.json.

    Returns:
        Mapping from institution name (e.g. "NBER") to OpenAlex institution ID
        (I-prefixed).
    """
    global _wp_institutions, _wp_ssrn_source
    if _wp_institutions is not None:
        return _wp_institutions

    try:
        data = json.loads(WP_SOURCES_PATH.read_text())
    except Exception as exc:
        log.warning("Could not load working_paper_sources.json: %s", exc)
        _wp_institutions = {}
        _wp_ssrn_source = None
        return _wp_institutions

    institutions = data.get("institutions", {})
    _wp_institutions = {k.upper(): v for k, v in institutions.items()}
    _wp_ssrn_source = data.get("ssrn_source_id")
    log.info("Loaded %d WP institution aliases from %s", len(_wp_institutions), WP_SOURCES_PATH)
    return _wp_institutions


def _title_to_alias(title: str) -> str:
    """Derive a short abbreviation from a journal title.

    Examples:
        "Journal of Political Economy"        → "JPE"
        "American Economic Review"              → "AER"
        "The Quarterly Journal of Economics"   → "QJE"
        "Journal of the European Economic Association" → "JEEA"
    """
    clean = title.split("/")[0].strip()

    if clean.startswith("The Annals of "):
        suffix_alias = _title_to_alias(clean[14:])
        return "Annals" + suffix_alias

    if clean.startswith("The "):
        clean = clean[4:]

    words = clean.split()
    STOP = {"of", "in", "for", "and", "the", "a", "an", "on", "at", "to", "by"}
    words = [w for w in words if w.lower() not in STOP and len(w) > 1]

    if not words:
        return clean[:4].upper()

    if len(words) == 1:
        return words[0][:4].upper()
    initials = "".join(w[0] for w in words[:-1])
    return (initials + words[-1][:3]).upper()


# ── Source resolution ──────────────────────────────────────────────────────────

def resolve_source(source: str | None) -> str | None:
    """Resolve a source/institution alias to an OpenAlex filter expression.

    Resolution order:
        1. Empty / None → unfiltered (return None)
        2. I-prefixed ID (institution) → return as-is for ``authorships.institutions.id``
        3. S-prefixed ID (source)      → return as-is for ``primary_location.source.id``
        4. ``SSRN``  → SSRN source ID from working_paper_sources.json
        5. Institution aliases (NBER, CEPR, …) → institution ID from working_paper_sources.json
        6. Journal aliases (JPE, AER, …)       → source ID from journal_list.json

    Returns:
        OpenAlex filter string, or None for no filter.
        For institutions returns the bare I-ID.
        For sources returns the bare S-ID.
        Callers construct the full filter expression.

    Raises:
        ValueError: Unrecognised alias with no mapping.
    """
    if not source:
        return None

    s = source.strip()
    upper = s.upper()

    if upper.startswith("I") and upper[1:].isdigit():
        return f"authorships.institutions.id:{s}"

    if upper.startswith("S") and upper[1:].isdigit():
        return f"primary_location.source.id:{s}"

    wp_aliases = _load_wp_institutions()

    if upper == "SSRN":
        ssrn = _wp_ssrn_source
        if not ssrn:
            raise ValueError(
                f"SSRN requested but ssrn_source_id not found in "
                f"{WP_SOURCES_PATH}. Check that working_paper_sources.json "
                f"is populated."
            )
        return ssrn

    if upper in wp_aliases:
        return wp_aliases[upper]

    journal_aliases = _load_journal_aliases()
    if upper in journal_aliases:
        return journal_aliases[upper]

    raise ValueError(
        f"Unknown source '{source}'. Check journal_list.json and "
        f"working_paper_sources.json for available aliases. "
        f"Sample journal aliases: NBER, CEPR, JPE, AER, QJE. "
        f"Sample institution aliases: I1321305853 (NBER), I4210140326 (CEPR)."
    )


def build_source_filter(source: str | None) -> str | None:
    """Build an OpenAlex ``filter=`` expression from a resolved source.

    Returns:
        OpenAlex filter string for use in API calls, e.g.
        ``primary_location.source.id:S18284184`` or
        ``authorships.institutions.id:I1321305853``.
        Returns None when source is None (no filter).
    """
    resolved = resolve_source(source)
    if not resolved:
        return None

    if resolved.startswith("I"):
        return f"authorships.institutions.id:{resolved}"
    if resolved.startswith("S"):
        return f"primary_location.source.id:{resolved}"
    return f"primary_location.source.id:{resolved}"


# ── HTTP session ──────────────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": f"paper-finder/1.0 (mailto:{OPENALEX_EMAIL})",
        "Accept": "application/json",
    })
    if OPENALEX_API_KEY:
        session.headers["Authorization"] = f"Bearer {OPENALEX_API_KEY}"
    return session


def _get(path: str, params: dict[str, Any], retries: int = 3) -> list[dict]:
    """GET ``path`` from OpenAlex, with retry-after-rate-limit."""
    session = _build_session()
    url = f"{OPENALEX_BASE_URL}{path}"
    for attempt in range(retries):
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            log.warning("Rate-limited. Waiting %ds (attempt %d/%d)", wait, attempt + 1, retries)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", []) if isinstance(data, dict) else data
    return []


# ── Public API ─────────────────────────────────────────────────────────────────

NBER_PROGRAM_KEYWORDS = {
    "Economic Fluctuations and Growth": ["business cycle", "growth", "fluctuations", "consumption", "investment"],
    "Development of the American Economy": ["history", "American economy", "development", "industrialization"],
    "Economics of Aging": ["aging", "retirement", "pension", "health", "elderly"],
    "Asset Pricing": ["asset pricing", "stock", "portfolio", "risk", "returns"],
    "Public Economics": ["public economics", "taxation", "government", "fiscal"],
    "Labor Studies": ["labor", "employment", "wage", "unemployment", "human capital"],
    "International Trade and Investment": ["trade", "international", "export", "import", "FDI"],
}


def parse_paper(raw: dict) -> dict:
    """Normalise a single OpenAlex paper dict to our canonical schema."""
    locations = raw.get("primary_location") or {}
    source = locations.get("source") or {}
    best_oa = raw.get("best_oa_location") or {}

    return {
        "id": raw.get("id"),
        "title": raw.get("title") or "Untitled",
        "authors": [a.get("author", {}).get("display_name", "") for a in raw.get("authorships", [])],
        "year": raw.get("publication_year"),
        "doi": raw.get("doi"),
        "source_title": source.get("display_name"),
        "source_id": source.get("id"),
        "cited_by_count": raw.get("cited_by_count", 0),
        "abstract": decode_abstract(raw.get("abstract_inverted_index") or {}),
        "openalex_url": raw.get("id"),
        "doi_url": raw.get("doi"),
        "oa_url": best_oa.get("landing_page_url"),
        "is_oa": bool(best_oa),
    }


def decode_abstract(inverted: dict | None) -> str:
    """Reconstruct plain text from OpenAlex inverted-index abstract."""
    if not inverted:
        return ""
    word_to_pos = inverted
    max_pos = max(pos for positions in word_to_pos.values() for pos in positions)
    tokens = [""] * (max_pos + 1)
    for word, positions in word_to_pos.items():
        for pos in positions:
            if 0 <= pos <= max_pos:
                tokens[pos] = word
    return " ".join(tokens)


def search_and_parse(keywords: list[str], per_page: int = 25, **kwargs) -> list[dict]:
    """Search and parse OpenAlex papers.

    Forwards ``source_ids`` (list of OpenAlex source IDs) to ``search_works``
    for multi-journal OR filtering.
    """
    papers = search_works(keywords, per_page=per_page, **kwargs)
    return [parse_paper(p) for p in papers]


def search_works(
    keywords: list[str],
    source: str | None = None,
    source_ids: list[str] | None = None,
    year: int | None = None,
    from_date: str | None = None,
    per_page: int = 25,
    sort: str = "cited_by_count:desc",
    fields: str = "id,title,display_name,authorships,publication_year,"
                 "cited_by_count,primary_location,best_oa_location,doi,abstract_inverted_index"
) -> list[dict]:
    """Search OpenAlex for works matching ``keywords`` with optional source filter.

    Args:
        keywords:   List of search terms (AND logic).
        source:     Source/institution alias, e.g. ``"NBER"``, ``"JPE"``, ``"SSRN"``,
                    or raw OpenAlex ID (``"S18284184"``, ``"I1321305853"``).
                    None → unfiltered global search.
        source_ids: List of OpenAlex source IDs (e.g. ``["S199447588", "S23254222"]``)
                    to filter by multiple journals using OR logic.
                    Takes precedence over ``source`` when both are provided.
        year:       Restrict to papers published in this year (single year).
        from_date:  Restrict to papers published from this date onwards (YYYY-MM-DD).
        per_page:   Results per page (OpenAlex max 200).
        sort:       Sort order. Defaults to "cited_by_count:desc".
                    Use "relevance_score:desc" for relevance-based ranking.
        fields:     Comma-separated list of fields to request from OpenAlex.

    Returns:
        List of raw OpenAlex paper dicts (use ``parse_paper()`` to normalise).
    """
    params: dict[str, Any] = {
        "per-page": min(per_page, 200),
        "filter": [],
        "sort": sort,
        "mailto": OPENALEX_EMAIL,
        "select": fields,
    }

    # Only set search param when there are actual keywords (empty search string
    # changes OpenAlex ranking behaviour and reduces results for sparse journals)
    if keywords:
        params["search"] = " ".join(keywords)

    # Multi-journal OR filter takes precedence over single source
    if source_ids:
        ids_or = "|".join(source_ids)
        params["filter"].append(f"primary_location.source.id:{ids_or}")
    elif source:
        src_filter = build_source_filter(source)
        if src_filter:
            params["filter"].append(src_filter)

    # When source_ids and from_date are both set, OpenAlex returns corrupt data
    # (authorships field is empty). We keep the API date filter (to get only recent
    # papers) but bump per_page to 200 to give us enough result volume despite
    # recent papers having zero citations. Authors are then extracted correctly
    # from the local post-filter step (parse_paper already runs after).
    local_date_filter_year: int | None = None
    if source_ids and from_date:
        local_date_filter_year = int(from_date[:4])
        params["per-page"] = 200
    if from_date:
        params["filter"].append(f"from_publication_date:{from_date}")

    if year:
        params["filter"].append(f"from_publication_year:{year}")

    if params["filter"]:
        params["filter"] = ",".join(params["filter"])
    else:
        del params["filter"]

    results = _get("/works", params)

    if local_date_filter_year is not None:
        filtered = [r for r in results if r.get("publication_year", 0) >= local_date_filter_year]
        results = filtered

    return [parse_paper(r) for r in results]
