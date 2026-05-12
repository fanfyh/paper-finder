#!/usr/bin/env python3
"""
Direct Zotero API → ChromaDB sync script.
Bypasses get_items_raw's zot.everything() which fetches ALL items before truncating.
Uses manual pagination with start= parameter to fetch only what we need.
"""
import argparse
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
LOG = logging.getLogger(__name__)

BATCH_SIZE = 100  # Zotero API page size


def main():
    parser = argparse.ArgumentParser(description="Sync Zotero items to ChromaDB")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--limit", type=int, default=1000, help="Max items to sync (default 1000)")
    parser.add_argument("--delay", type=float, default=0.12, help="Delay between API calls (rate limit)")
    args = parser.parse_args()

    import sys
    from pathlib import Path
    # Add project root to path so 'src' module resolves
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Lazy imports to keep CLI fast
    import json

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)

    zotero_cfg = cfg.get("zotero", {})
    semantic_cfg = cfg.get("semantic_search", {})

    library_id = zotero_cfg.get("library_id")
    api_key = zotero_cfg.get("api_key")
    library_type = zotero_cfg.get("library_type", "user")

    import httpx

    headers = {
        "Zotero-API-Key": api_key,
        "Zotero-API-Version": "3",
    }

    # Test API connection
    resp = httpx.get(
        f"https://api.zotero.org/{library_type}s/{library_id}/items/top?limit=1",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    total_results = int(resp.headers.get("Total-Results", 0))
    LOG.info(f"Zotero library has {total_results} total items")

    # ChromaDB setup
    from src.codex_research_assist.zotero_mcp.semantic_search import create_semantic_search

    ss = create_semantic_search(args.config)
    LOG.info(f"ChromaDB collection: {ss.chroma_client.collection_name}, "
             f"current docs: {ss.chroma_client.collection.count()}")

    # Counters
    processed = 0
    errors = 0
    start_idx = 0
    max_items = min(args.limit, total_results)

    while processed < max_items:
        batch_start = time.time()
        this_batch = min(BATCH_SIZE, max_items - processed)

        url = (f"https://api.zotero.org/{library_type}s/{library_id}/items/top"
               f"?limit={this_batch}&start={processed}&format=json")
        try:
            resp = httpx.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            LOG.error(f"  Failed to fetch batch at offset {processed}: {exc}")
            errors += 1
            processed += this_batch
            continue

        items = resp.json()
        if not items:
            break

        ids, documents, metadatas = [], [], []
        for item in items:
            key = item.get("key") or item.get("data", {}).get("key", "")
            if not key:
                continue
            ids.append(key)
            documents.append(ss._create_document_text(item))
            metadatas.append(ss._create_metadata(item))

        if documents:
            ss.chroma_client.upsert_documents(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        processed += len(items)
        LOG.info(f"  [{processed}/{max_items}] batch OK ({len(items)} items, "
                 f"{time.time()-batch_start:.1f}s)")

        if processed < max_items:
            time.sleep(args.delay)

    LOG.info(f"\nDone. Processed={processed}, Errors={errors}")
    LOG.info(f"ChromaDB now has {ss.chroma_client.collection.count()} documents")

    # Save last_update
    from datetime import datetime
    ss.update_config["last_update"] = datetime.now().isoformat()
    ss._save_update_config()
    LOG.info("Update timestamp saved.")


if __name__ == "__main__":
    main()
