"""OpenAlex API client for NBER working papers."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

LOG = logging.getLogger(__name__)

OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_API_KEY = os.getenv("OPENALEX_KEY", "")
NBER_REPOSITORY_ID = "S2809516038"

DEFAULT_TIMEOUT = float(os.getenv("OPENALEX_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("OPENALEX_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("OPENALEX_RETRY_DELAY", "1"))

HEADERS = {
    "User-Agent": "paper-finder/0.1.0 (+https://github.com/user/paper-finder)",
    "Accept": "application/json",
    "Mailto": "paper-finder@example.com"
}

# NBER Program to Keywords mapping
NBER_PROGRAM_KEYWORDS = {
    # Research Programs (19)
    "AG": ["aging", "retirement", "elderly", "pension"],
    "AP": ["asset pricing", "financial markets", "stock", "portfolio"],
    "CH": ["children", "family", "fertility", "child development"],
    "CF": ["corporate finance", "firm", "investment", "capital structure"],
    "DEV": ["development", "poverty", "economic development", "growth"],
    "DAE": ["american economy", "historical", "us economy"],
    "EFG": ["economic fluctuations", "business cycle", "recession"],
    "ED": ["education", "school", "human capital", "schooling"],
    "HE": ["health", "medical", "healthcare", "health economics"],
    "EEE": ["environment", "climate", "energy", "carbon", "emissions"],
    "IO": ["industrial organization", "competition", "market power"],
    "IFM": ["international macro", "exchange rate", "balance of payments"],
    "ITI": ["trade", "international trade", "tariff", "exports"],
    "LS": ["labor", "employment", "wage", "unemployment"],
    "LE": ["law", "legal", "litigation"],
    "ME": ["monetary", "money", "inflation", "federal reserve"],
    "POL": ["political economy", "voting", "electoral", "government"],
    "PE": ["public economics", "tax", "fiscal", "government spending"],
    "PRO": ["innovation", "entrepreneurship", "productivity", "technology"],

    # Working Groups (13)
    "BF": ["behavioral finance", "behavioral economics", "finance psychology"],
    "CN": ["China", "Chinese economy", "China housing"],
    "EC": ["crime", "criminal", "incarceration"],
    "EN": ["entrepreneurship", "startup", "new venture"],
    "GE": ["gender", "women", "sex", "gender gap"],
    "HF": ["household finance", "household", "wealth"],
    "IP": ["innovation policy", "R&D", "patent"],
    "INS": ["insurance", "risk", "uncertainty"],
    "MD": ["market design", "matching", "auction", "mechanism design"],
    "OE": ["organizational economics", "organization", "firm organization"],
    "PE_O": ["personnel", "human resources", "worker"],
    "RS": ["race", "racial", "discrimination", "inequality"],
    "UR": ["urban", "city", "spatial", "regional", "housing"],
}


def _build_session() -> requests.Session:
    """Build a requests session with proxy support."""
    session = requests.Session()
    session.headers.update(HEADERS)

    proxy_url = os.getenv("OPENALEX_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if proxy_url:
        http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or proxy_url
        session.proxies = {"http": http_proxy, "https": proxy_url}
        session.verify = False
        LOG.info("Using proxy: %s", proxy_url)

    return session


SESSION = _build_session()


def _retry_request(url: str, **kwargs) -> requests.Response:
    """Make a request with retry logic."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(url, **kwargs)
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            LOG.warning("OpenAlex request failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
        except requests.HTTPError as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code and 400 <= status_code < 500:
                raise
            last_error = exc
            LOG.warning("OpenAlex HTTP error (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    if last_error:
        raise last_error
    raise RuntimeError("Unknown OpenAlex request error")


def search_nber_papers(
    keywords: list[str] | None = None,
    program: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    per_page: int = 25,
    page: int = 1,
    sort: str = "publication_date:desc",
) -> dict[str, Any]:
    """Search NBER working papers via OpenAlex.

    Args:
        keywords: List of keywords to search
        program: NBER program code (e.g., "CN", "PE", "UR")
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        per_page: Results per page
        page: Page number
        sort: Sort order

    Returns:
        Dict with meta and results
    """
    # Build filter
    filters = [f"primary_location.source.id:{NBER_REPOSITORY_ID}"]

    if from_date:
        filters.append(f"from_publication_date:{from_date}")
    if to_date:
        filters.append(f"to_publication_date:{to_date}")

    filter_str = ",".join(filters)

    # Build search query
    search_parts = []

    # Add program keywords if specified
    if program:
        program_kw = NBER_PROGRAM_KEYWORDS.get(program.upper(), [])
        search_parts.extend(program_kw)

    # Add user keywords
    if keywords:
        search_parts.extend(keywords)

    search_query = " ".join(f'"{k}"' if " " in k else k for k in search_parts) if search_parts else ""

    # Build URL
    params = {
        "filter": filter_str,
        "per_page": per_page,
        "page": page,
        "sort": sort,
    }

    if search_query:
        params["search"] = search_query

    # Add API key if available
    headers = dict(HEADERS)
    if OPENALEX_API_KEY:
        headers["Authorization"] = f"Bearer {OPENALEX_API_KEY}"

    url = f"{OPENALEX_BASE_URL}/works"

    LOG.info("Searching OpenAlex: %s", params)

    response = _retry_request(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
    data = response.json()

    return data


def decode_abstract(inverted_index: dict[str, list[int]]) -> str:
    """Decode OpenAlex abstract_inverted_index to plain text.

    Args:
        inverted_index: OpenAlex abstract_inverted_index dict

    Returns:
        Decoded abstract text
    """
    if not inverted_index:
        return ""

    # Group words by position
    positions: dict[int, list[str]] = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            if pos not in positions:
                positions[pos] = []
            positions[pos].append(word)

    # Reconstruct text in position order
    sorted_positions = sorted(positions.keys())
    words = []
    for pos in sorted_positions:
        words.extend(positions[pos])

    return " ".join(words)


def parse_paper(result: dict[str, Any]) -> dict[str, Any]:
    """Parse OpenAlex work result to paper dict.

    Args:
        result: OpenAlex work result

    Returns:
        Parsed paper dict
    """
    # Extract NBER ID from DOI
    doi = result.get("doi", "")
    nber_id = ""
    if "10.3386/w" in doi:
        match = re.search(r"10\.3386/(w\d+)", doi)
        if match:
            nber_id = match.group(1)

    # Decode abstract
    abstract = ""
    inverted = result.get("abstract_inverted_index", {})
    if inverted:
        abstract = decode_abstract(inverted)

    # Extract authors
    authors = []
    for auth in result.get("authorships", []):
        name = auth.get("author", {}).get("display_name", "")
        if name:
            institutions = auth.get("institutions", [])
            inst_name = institutions[0].get("display_name", "") if institutions else ""
            authors.append({"name": name, "institution": inst_name})

    # Extract concepts (topics)
    concepts = []
    for c in result.get("concepts", []):
        concepts.append({
            "id": c.get("id", ""),
            "name": c.get("display_name", ""),
            "score": c.get("score", 0),
        })

    # Extract primary location URL
    primary_url = ""
    primary_loc = result.get("primary_location", {})
    if primary_loc:
        primary_url = primary_loc.get("landing_page_url", "")

    return {
        "nber_id": nber_id,
        "doi": doi,
        "title": result.get("title", ""),
        "authors": authors,
        "abstract": abstract,
        "publication_date": result.get("publication_date", ""),
        "publication_year": result.get("publication_year"),
        "concepts": concepts,
        "cited_by_count": result.get("cited_by_count", 0),
        "url": primary_url,
        "type": result.get("type", ""),
        "openalex_id": result.get("id", ""),
    }


def search_and_parse(
    keywords: list[str] | None = None,
    program: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    per_page: int = 25,
) -> list[dict[str, Any]]:
    """Search and parse NBER papers.

    Args:
        keywords: Keywords to search
        program: NBER program code
        from_date: Start date
        to_date: End date
        per_page: Max results

    Returns:
        List of parsed paper dicts
    """
    data = search_nber_papers(
        keywords=keywords,
        program=program,
        from_date=from_date,
        to_date=to_date,
        per_page=per_page,
    )

    papers = []
    for result in data.get("results", []):
        try:
            paper = parse_paper(result)
            papers.append(paper)
        except Exception as exc:
            LOG.warning("Failed to parse paper: %s", exc)

    return papers


def search_journal_papers(
    source_id: str,
    keywords: list[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    per_page: int = 25,
    page: int = 1,
    sort: str = "publication_date:desc",
) -> list[dict[str, Any]]:
    """Search papers from a specific journal via OpenAlex.

    Args:
        source_id: OpenAlex source ID (e.g., S95323914 for JPE)
        keywords: List of keywords to search
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        per_page: Results per page
        page: Page number
        sort: Sort order

    Returns:
        List of parsed paper dicts
    """
    # Build filter
    filters = [f"primary_location.source.id:{source_id}"]

    if from_date:
        filters.append(f"from_publication_date:{from_date}")
    if to_date:
        filters.append(f"to_publication_date:{to_date}")

    filter_str = ",".join(filters)

    # Build search query
    search_query = " ".join(f'"{k}"' if " " in k else k for k in keywords) if keywords else ""

    # Build URL
    params = {
        "filter": filter_str,
        "per_page": per_page,
        "page": page,
        "sort": sort,
    }

    if search_query:
        params["search"] = search_query

    # Add API key if available
    headers = dict(HEADERS)
    if OPENALEX_API_KEY:
        headers["Authorization"] = f"Bearer {OPENALEX_API_KEY}"

    url = f"{OPENALEX_BASE_URL}/works"

    LOG.info("Searching OpenAlex journal: %s", params)

    response = _retry_request(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
    data = response.json()

    # Parse papers (reuse same parsing logic)
    papers = []
    for result in data.get("results", []):
        try:
            paper = parse_paper(result)
            papers.append(paper)
        except Exception as exc:
            LOG.warning("Failed to parse paper: %s", exc)

    return papers


def search_works(
    keywords: list[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    per_page: int = 25,
    page: int = 1,
    sort: str = "publication_date:desc",
    concepts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search all papers via OpenAlex without source restrictions.

    Args:
        keywords: List of keywords to search
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        per_page: Results per page
        page: Page number
        sort: Sort order
        concepts: OpenAlex concept IDs to filter by (e.g., for sociology)

    Returns:
        List of parsed paper dicts
    """
    # Build filter
    filters = []

    if from_date:
        filters.append(f"from_publication_date:{from_date}")
    if to_date:
        filters.append(f"to_publication_date:{to_date}")

    if concepts:
        filters.append(f"concepts.id:{','.join(concepts)}")

    filter_str = ",".join(filters) if filters else ""

    # Build search query
    search_query = " ".join(f'"{k}"' if " " in k else k for k in keywords) if keywords else ""

    # Build URL
    params = {
        "per_page": per_page,
        "page": page,
        "sort": sort,
    }

    if filter_str:
        params["filter"] = filter_str
    if search_query:
        params["search"] = search_query

    # Add API key if available
    headers = dict(HEADERS)
    if OPENALEX_API_KEY:
        headers["Authorization"] = f"Bearer {OPENALEX_API_KEY}"

    url = f"{OPENALEX_BASE_URL}/works"

    LOG.info("Searching OpenAlex (all sources): %s", params)

    response = _retry_request(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
    data = response.json()

    # Parse papers (reuse same parsing logic)
    papers = []
    for result in data.get("results", []):
        try:
            paper = parse_paper(result)
            # Add source info
            primary_loc = result.get("primary_location", {})
            source = primary_loc.get("source", {})
            paper["_source"] = source.get("display_name", "Unknown")
            papers.append(paper)
        except Exception as exc:
            LOG.warning("Failed to parse paper: %s", exc)

    return papers
