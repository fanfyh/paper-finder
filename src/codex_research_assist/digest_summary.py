from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def summary_output_path(output_root: Path, digest_json_path: Path) -> Path:
    return output_root / f"{digest_json_path.stem}.run-summary.json"


def write_digest_run_summary(
    *,
    action: str,
    digest_json_path: Path,
    candidate_paths: list[Path],
    html_path: Path,
    email_json_path: Path | None,
    telegram_json_path: Path | None,
    output_root: Path,
    profile_path: Path | None,
) -> Path:
    summary_path = summary_output_path(output_root, digest_json_path)
    payload = {
        "schema_version": "1.0.0",
        "run": {
            "component": "paper-finder",
            "action": action,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile_path": profile_path.as_posix() if profile_path is not None else None,
            "output_root": output_root.as_posix(),
            "candidate_count": len(candidate_paths),
        },
        "artifacts": {
            "digest_json_path": digest_json_path.as_posix(),
            "candidate_paths": [path.as_posix() for path in candidate_paths],
            "html_path": html_path.as_posix(),
            "email_json_path": email_json_path.as_posix() if email_json_path is not None else None,
            "telegram_json_path": telegram_json_path.as_posix() if telegram_json_path is not None else None,
            "summary_path": summary_path.as_posix(),
        },
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path
