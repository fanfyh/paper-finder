#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_research_assist.controller.profile_refresh_policy import evaluate_profile_refresh_policy
from codex_research_assist.openclaw_runner import (
    action_digest,
    action_render_digest,
    create_temp_toml_config,
    get_output_root,
    get_profile_path,
    load_config,
)
from codex_research_assist.zotero_mcp.config import load_zotero_config
from codex_research_assist.zotero_mcp.server import (
    zotero_get_search_database_status,
    zotero_list_local_groups,
    zotero_profile_evidence,
    zotero_semantic_search,
    zotero_status,
    zotero_update_search_database,
)


def _utc_now_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _sanitize_config(config: dict[str, Any], zotero_cfg: Any) -> dict[str, Any]:
    payload = json.loads(json.dumps(config))
    zotero_block = payload.get("zotero")
    if isinstance(zotero_block, dict) and zotero_block.get("api_key"):
        zotero_block["api_key"] = "***masked***"
    payload["_resolved"] = {
        "config_path": zotero_cfg.config_path.as_posix(),
        "profile_path": zotero_cfg.profile_path.as_posix(),
        "semantic_zotero_db_path": zotero_cfg.semantic_zotero_db_path.as_posix()
        if zotero_cfg.semantic_zotero_db_path
        else None,
        "semantic_persist_directory": zotero_cfg.semantic_persist_directory.as_posix(),
    }
    return payload


def _write_json(target: Path, payload: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _runtime_root(config_path: Path, run_id: str | None) -> Path:
    base_dir = config_path.expanduser().resolve().parent
    return base_dir / "runtime" / (run_id or _utc_now_slug())


def _policy_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    profile_path = get_profile_path(config)
    output_root = get_output_root(config)
    temp_toml_path = create_temp_toml_config(config, profile_path, output_root)
    try:
        return evaluate_profile_refresh_policy(config_path=temp_toml_path, profile_override=None)
    finally:
        try:
            temp_toml_path.unlink()
        except Exception:
            pass


def run_stage(
    *,
    stage: str,
    config_path: Path,
    config: dict[str, Any],
    runtime_root: Path,
    evidence_limit: int,
    semantic_limit: int,
    semantic_query: str,
    index_limit: int,
    force_rebuild: bool,
    digest_json: Path | None,
) -> dict[str, Any]:
    config_path_str = config_path.as_posix()

    if stage == "config":
        zotero_cfg = load_zotero_config(config_path)
        payload = _sanitize_config(config, zotero_cfg)
        _write_json(runtime_root / "01-config.snapshot.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "01-config.snapshot.json").as_posix(),
        }

    if stage == "profile-policy":
        payload = _policy_snapshot(config)
        _write_json(runtime_root / "02-profile-policy.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "02-profile-policy.json").as_posix(),
            "refresh_required": payload.get("controller", {}).get("profile_refresh", {}).get("required"),
        }

    if stage == "zotero-status":
        payload = zotero_status(config_path=config_path_str)
        _write_json(runtime_root / "03-zotero-status.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "03-zotero-status.json").as_posix(),
            "configured": payload.get("zotero_configured"),
        }

    if stage == "local-groups":
        payload = zotero_list_local_groups(config_path=config_path_str)
        _write_json(runtime_root / "04-local-groups.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "04-local-groups.json").as_posix(),
            "count": len(payload),
        }

    if stage == "profile-evidence":
        payload = zotero_profile_evidence(config_path=config_path_str, limit=evidence_limit)
        _write_json(runtime_root / "05-profile-evidence.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "05-profile-evidence.json").as_posix(),
            "item_count": payload.get("item_count"),
        }

    if stage == "semantic-status":
        payload = zotero_get_search_database_status(config_path=config_path_str)
        _write_json(runtime_root / "06-semantic-status.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "06-semantic-status.json").as_posix(),
        }

    if stage == "semantic-update":
        payload = zotero_update_search_database(
            config_path=config_path_str,
            force_rebuild=force_rebuild,
            limit=index_limit,
        )
        _write_json(runtime_root / "07-semantic-update.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "07-semantic-update.json").as_posix(),
            "indexed_items": payload.get("indexed_items"),
        }

    if stage == "semantic-search":
        payload = zotero_semantic_search(
            query=semantic_query,
            config_path=config_path_str,
            limit=semantic_limit,
        )
        _write_json(runtime_root / "08-semantic-search.json", payload)
        return {
            "stage": stage,
            "output": (runtime_root / "08-semantic-search.json").as_posix(),
            "result_count": len(payload.get("results", [])) if isinstance(payload, dict) else None,
        }

    if stage == "digest":
        output = action_digest(config, fmt="markdown")
        _write_text(runtime_root / "09-digest.stdout.md", output)
        return {
            "stage": stage,
            "output": (runtime_root / "09-digest.stdout.md").as_posix(),
            "reports_root": get_output_root(config).as_posix(),
        }

    if stage == "render-digest":
        if digest_json is None:
            raise ValueError("digest_json is required for render-digest stage")
        output = action_render_digest(config, digest_json, fmt="markdown")
        _write_text(runtime_root / "10-render-digest.stdout.md", output)
        return {
            "stage": stage,
            "output": (runtime_root / "10-render-digest.stdout.md").as_posix(),
            "reports_root": get_output_root(config).as_posix(),
        }

    raise ValueError(f"Unsupported stage: {stage}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce real Zotero-backed research-assist stages")
    parser.add_argument("--config", type=Path, required=True, help="Path to local repro config JSON")
    parser.add_argument(
        "--stage",
        choices=[
            "config",
            "profile-policy",
            "zotero-status",
            "local-groups",
            "profile-evidence",
            "semantic-status",
            "semantic-update",
            "semantic-search",
            "digest",
            "render-digest",
            "all",
        ],
        default="all",
        help="Which stage to run",
    )
    parser.add_argument("--run-id", type=str, default=None, help="Optional run directory name under runtime/")
    parser.add_argument("--evidence-limit", type=int, default=50, help="Limit for zotero_profile_evidence")
    parser.add_argument("--semantic-limit", type=int, default=5, help="Top K for semantic search")
    parser.add_argument("--semantic-query", type=str, default="physics informed neural network", help="Semantic search query")
    parser.add_argument("--index-limit", type=int, default=500, help="Max Zotero items to index during semantic update")
    parser.add_argument("--force-rebuild", action="store_true", help="Force semantic index rebuild")
    parser.add_argument("--digest-json", type=Path, default=None, help="Digest manifest path for render-digest")
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve()
    config = load_config(config_path)
    runtime_root = _runtime_root(config_path, args.run_id)
    runtime_root.mkdir(parents=True, exist_ok=True)

    stage_order = [
        "config",
        "profile-policy",
        "zotero-status",
        "local-groups",
        "profile-evidence",
        "semantic-status",
    ]
    if args.stage == "all":
        stages = stage_order
    else:
        stages = [args.stage]

    results: list[dict[str, Any]] = []
    for stage in stages:
        results.append(
            run_stage(
                stage=stage,
                config_path=config_path,
                config=config,
                runtime_root=runtime_root,
                evidence_limit=max(1, args.evidence_limit),
                semantic_limit=max(1, args.semantic_limit),
                semantic_query=args.semantic_query,
                index_limit=max(1, args.index_limit),
                force_rebuild=args.force_rebuild,
                digest_json=args.digest_json.expanduser().resolve() if args.digest_json else None,
            )
        )

    summary = {
        "run_id": runtime_root.name,
        "config_path": config_path.as_posix(),
        "runtime_root": runtime_root.as_posix(),
        "stages": results,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _write_json(runtime_root / "run-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
