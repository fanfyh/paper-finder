from __future__ import annotations

import argparse
import json
import math
import tomllib
from datetime import UTC, datetime
from pathlib import Path


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as file_handle:
        return tomllib.load(file_handle)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _resolve_profile_path(config_path: Path, profile_override: str | None) -> Path:
    if profile_override:
        return Path(profile_override)
    config = _load_toml(config_path)
    return Path(str(config.get("profile_path") or "profiles/research-interest.json"))


def evaluate_profile_refresh_policy(
    *,
    config_path: Path,
    profile_override: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    config = _load_toml(config_path)
    resolved_profile_path = _resolve_profile_path(config_path, profile_override)
    controller_config = dict(config.get("controller") or {})
    profile_refresh_config = dict(controller_config.get("profile_refresh") or {})
    max_age_days = int(profile_refresh_config.get("max_age_days") or 7)
    refresh_enabled = bool(profile_refresh_config.get("enabled", True))
    refresh_if_missing = bool(profile_refresh_config.get("refresh_if_missing", True))
    current_time = (now or datetime.now(UTC)).astimezone(UTC)

    exists = resolved_profile_path.exists()
    updated_at_text: str | None = None
    updated_at: datetime | None = None
    profile_age_days: float | None = None
    required = False
    reason = "fresh"

    if not exists:
        required = refresh_if_missing
        reason = "missing_profile" if required else "missing_profile_refresh_disabled"
    else:
        try:
            payload = json.loads(resolved_profile_path.read_text(encoding="utf-8"))
        except Exception:
            required = True
            reason = "unreadable_profile"
        else:
            updated_at_text = str(payload.get("updated_at") or "").strip() or None
            updated_at = _parse_datetime(updated_at_text)
            if updated_at is None:
                required = True
                reason = "invalid_updated_at"
            else:
                age_seconds = max(0.0, (current_time - updated_at).total_seconds())
                profile_age_days = age_seconds / 86400.0
                if not refresh_enabled:
                    required = False
                    reason = "refresh_disabled"
                elif profile_age_days >= float(max_age_days):
                    required = True
                    reason = "stale_profile"
                else:
                    required = False
                    reason = "fresh"

    stage_plan = [
        {
            "stage": "profile_update",
            "enabled": required,
            "reason": reason,
        },
        {
            "stage": "retrieval",
            "enabled": True,
            "reason": "always_run",
        },
        {
            "stage": "review",
            "enabled": True,
            "reason": "always_run",
        },
    ]

    rounded_age_days = None if profile_age_days is None else round(profile_age_days, 3)
    age_days_ceiling = None if profile_age_days is None else math.ceil(profile_age_days)
    return {
        "schema_version": "1.0.0",
        "config_path": config_path.as_posix(),
        "profile_path": resolved_profile_path.as_posix(),
        "profile_exists": exists,
        "profile_updated_at": updated_at_text,
        "profile_age_days": rounded_age_days,
        "profile_age_days_ceiling": age_days_ceiling,
        "controller": {
            "profile_refresh": {
                "enabled": refresh_enabled,
                "refresh_if_missing": refresh_if_missing,
                "max_age_days": max_age_days,
                "required": required,
                "reason": reason,
            },
        },
        "stage_plan": stage_plan,
        "evaluated_at": current_time.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate controller-side profile refresh policy")
    parser.add_argument("--config", required=True, help="Path to the pipeline TOML config")
    parser.add_argument("--profile", default=None, help="Optional profile override path")
    args = parser.parse_args()

    result = evaluate_profile_refresh_policy(
        config_path=Path(args.config),
        profile_override=args.profile,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
