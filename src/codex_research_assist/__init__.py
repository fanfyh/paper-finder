"""paper-finder — research paper discovery and digest."""

from .client import (
    NBER_PROGRAM_KEYWORDS,
    decode_abstract,
    parse_paper,
    resolve_source,
    search_and_parse,
    search_works,
)
from .pipeline import (
    _generate_candidate_markdown,
    incremental_sync,
    load_cache,
    run_openalex_pipeline,
    run_search,
    save_cache,
)

__all__ = [
    "__version__",
    # client
    "search_works",
    "search_and_parse",
    "resolve_source",
    "parse_paper",
    "decode_abstract",
    "NBER_PROGRAM_KEYWORDS",
    # pipeline
    "run_search",
    "incremental_sync",
    "load_cache",
    "save_cache",
    "run_openalex_pipeline",
    "_generate_candidate_markdown",
]

__version__ = "0.1.0"
