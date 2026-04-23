#!/usr/bin/env python3
"""CLI entry point for paper-finder.

Pure CLI that outputs markdown/HTML to stdout.

Usage:
    python3 -m codex_research_assist.openclaw_runner --action search --query "fiscal" --source nber --top 20
    python3 -m codex_research_assist.openclaw_runner --action digest-all --config ~/.claude/tools/paper-finder/config.json
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
from .nber_pipeline.pipeline import run_nber_pipeline
from .digest_summary import write_digest_run_summary
from .email_sender import send_email
from .ranker import rank_candidates
from .review_digest import enrich_candidates_with_system_review
from .html_fmt import format_digest_html, format_search_html
from .telegram_fmt import format_digest_telegram, format_search_telegram
from .telegram_sender import send_digest
from .zotero_mcp.semantic_search import create_semantic_search
from .zotero_mcp.chroma_client import ChromaClient

import os
import requests

LOG = logging.getLogger("openclaw_runner")

DEFAULT_CONFIG_DIR = Path.home() / ".claude" / "tools" / "paper-finder"
DEFAULT_CONFIG = DEFAULT_CONFIG_DIR / "config.json"


def _config_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _review_fallback_to_system(config: dict) -> bool:
    review_cfg = config.get("review_generation", {})
    if not isinstance(review_cfg, dict):
        return True
    return _config_bool(review_cfg.get("fallback_to_system", True), True)


def _semantic_search_enabled(config: dict) -> bool:
    semantic_cfg = config.get("semantic_search", {})
    if not isinstance(semantic_cfg, dict):
        return True
    return _config_bool(semantic_cfg.get("enabled", True), True)


def _telegram_send_enabled(config: dict) -> bool:
    delivery_cfg = config.get("delivery", {})
    if not isinstance(delivery_cfg, dict):
        return False
    telegram_cfg = delivery_cfg.get("telegram", {})
    if not isinstance(telegram_cfg, dict):
        return False
    return _config_bool(telegram_cfg.get("send_enabled", False), False)


def _email_config(config: dict) -> dict:
    delivery_cfg = config.get("delivery", {})
    if not isinstance(delivery_cfg, dict):
        return {}
    email_cfg = delivery_cfg.get("email", {})
    if not isinstance(email_cfg, dict):
        return {}
    return email_cfg


def _email_send_enabled(config: dict) -> bool:
    return _config_bool(_email_config(config).get("send_enabled", False), False)


def _primary_delivery_channel(config: dict) -> str:
    delivery_cfg = config.get("delivery", {})
    if not isinstance(delivery_cfg, dict):
        return "email"
    value = str(delivery_cfg.get("primary_channel", "email")).strip().lower()
    if value in {"email", "telegram"}:
        return value
    return "email"


def _telegram_fallback_on_failure(config: dict) -> bool:
    return _config_bool(_email_config(config).get("telegram_fallback_on_failure", True), True)


def _email_write_metadata(config: dict) -> bool:
    return _config_bool(_email_config(config).get("write_metadata", True), True)


def _email_subject(config: dict, *, action_name: str, date_str: str) -> str:
    email_cfg = _email_config(config)
    prefix = str(email_cfg.get("subject_prefix", "[paper-finder]")).strip() or "[paper-finder]"
    action_label = "Search Results"
    return f"{prefix} {action_label} {date_str}"


def _digest_email_subject(config: dict, *, date_str: str, candidates: list[dict]) -> str:
    prefix = str(_email_config(config).get("subject_prefix", "[paper-finder]")).strip() or "[paper-finder]"
    short_date = _display_date(date_str)
    read_first_count = sum(
        1
        for candidate in candidates
        if str((candidate.get("review") or {}).get("recommendation") or "").strip() == "read_first"
    )
    if candidates:
        lead_title = str(candidates[0].get("paper", {}).get("title") or "top picks").strip()
        if len(lead_title) > 48:
            lead_title = lead_title[:47].rstrip() + "..."
    else:
        lead_title = "digest ready"
    return f"{prefix} {read_first_count} read-first picks | {lead_title} | {short_date}"


def _search_email_subject(config: dict, *, date_str: str, query: str, paper_count: int) -> str:
    prefix = str(_email_config(config).get("subject_prefix", "[paper-finder]")).strip() or "[paper-finder]"
    short_date = _display_date(date_str)
    short_query = query.strip()
    if len(short_query) > 42:
        short_query = short_query[:41].rstrip() + "..."
    return f"{prefix} {paper_count} search results | {short_query} | {short_date}"


def _email_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _display_date(date_str: str) -> str:
    if len(date_str) >= 10 and date_str[4] == "-" and date_str[7] == "-":
        return f"{date_str[5:7]}/{date_str[8:10]}"
    return date_str


def _load_profile_summary(profile_path: Path | None, config: dict) -> dict[str, object]:
    profile_labels: list[str] = []
    updated_at = ""
    if profile_path is not None and profile_path.exists():
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            updated_at = str(payload.get("updated_at") or payload.get("generated_at") or "").strip()
            for interest in payload.get("interests", []):
                if not isinstance(interest, dict):
                    continue
                if interest.get("enabled", True) is False:
                    continue
                label = str(interest.get("label") or interest.get("interest_label") or "").strip()
                if label:
                    profile_labels.append(label)
        except Exception as exc:
            LOG.warning("Failed to load profile summary from %s: %s", profile_path, exc)

    retrieval_defaults = config.get("retrieval_defaults", {})
    refresh_days = None
    if isinstance(retrieval_defaults, dict):
        value = retrieval_defaults.get("max_age_days")
        if isinstance(value, int) and value > 0:
            refresh_days = value
        elif isinstance(value, str) and value.strip().isdigit():
            refresh_days = int(value.strip())

    return {
        "labels": profile_labels[:6],
        "updated_at": updated_at,
        "refresh_days": refresh_days,
    }


def _format_digest_email_body(
    candidates: list[dict],
    *,
    date_str: str,
    html_path: Path,
    profile_summary: dict[str, object] | None = None,
) -> tuple[str, str]:
    read_first_count = sum(
        1
        for candidate in candidates
        if str((candidate.get("review") or {}).get("recommendation") or "").strip() == "read_first"
    )
    skim_count = sum(
        1
        for candidate in candidates
        if str((candidate.get("review") or {}).get("recommendation") or "").strip() == "skim"
    )
    themes = sorted(
        {
            str(tag)
            for candidate in candidates
            for tag in ((candidate.get("triage") or {}).get("matched_interest_labels") or [])
            if str(tag).strip()
        }
    )
    lead_title = str(candidates[0].get("paper", {}).get("title") or "Digest attached").strip() if candidates else "Digest attached"
    lead_reason = ""
    if candidates:
        lead_reason = str((candidates[0].get("review") or {}).get("why_it_matters") or "").strip()
    if len(lead_reason) > 140:
        lead_reason = lead_reason[:139].rstrip() + "..."
    theme_line = ", ".join(themes[:3]) if themes else "No strong theme labels"
    short_date = _display_date(date_str)
    profile_summary = profile_summary or {}
    profile_labels = [str(label) for label in (profile_summary.get("labels") or []) if str(label).strip()]
    profile_updated_at = _display_date(str(profile_summary.get("updated_at") or "")[:10]) if profile_summary.get("updated_at") else "unknown"
    refresh_days = profile_summary.get("refresh_days")
    refresh_text = f"every {refresh_days} days" if isinstance(refresh_days, int) and refresh_days > 0 else "manual"
    profile_line = ", ".join(profile_labels[:4]) if profile_labels else "No active profile labels"

    plain = "\n".join(
        [
            f"Research Digest | {short_date}",
            "",
            f"Selected papers: {len(candidates)}",
            f"Read first: {read_first_count}",
            f"Skim: {skim_count}",
            f"Themes: {theme_line}",
            "",
            f"Profile: {profile_line}",
            f"Profile updated: {profile_updated_at}",
            f"Refresh cadence: {refresh_text}",
            "",
            f"Lead paper: {lead_title}",
            lead_reason or "The attached HTML digest contains the full reading cards.",
            "",
            f"Attachment: {html_path.name}",
            "Open the attached HTML file in a browser for the full styled digest.",
        ]
    )

    html = f"""\
<html>
  <body style="margin:0;padding:0;background:#f6ede1;color:#2f241d;font-family:Arial,'Helvetica Neue',sans-serif;">
    <div style="max-width:640px;margin:0 auto;padding:24px 18px;">
      <div style="background:#fffaf3;border:1px solid #e6d6c4;border-radius:18px;padding:24px 22px;">
        <div style="font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:#8f4b2e;font-weight:700;margin-bottom:12px;">Research Assist Digest</div>
        <h1 style="margin:0 0 10px;font-size:30px;line-height:1.1;color:#2f241d;">Your digest is ready</h1>
        <p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#5a4a3e;">Quick triage here. Open the attached HTML file for the full card view.</p>
        <div style="border-radius:16px;background:#f9f2e8;border:1px solid #ecd8c3;padding:16px 16px 14px;margin:0 0 18px;">
          <div style="font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:#8f4b2e;font-weight:700;margin-bottom:8px;">Current profile</div>
          <div style="font-size:14px;line-height:1.6;color:#2f241d;font-weight:600;margin-bottom:10px;">{_email_escape(profile_line)}</div>
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;">
            <tr>
              <td style="width:50%;padding:0 8px 0 0;vertical-align:top;">
                <div style="font-size:11px;letter-spacing:1.1px;text-transform:uppercase;color:#8a7465;margin-bottom:4px;">Updated</div>
                <div style="font-size:15px;line-height:1.35;color:#2f241d;font-weight:700;">{_email_escape(profile_updated_at)}</div>
              </td>
              <td style="width:50%;padding:0 0 0 8px;vertical-align:top;">
                <div style="font-size:11px;letter-spacing:1.1px;text-transform:uppercase;color:#8a7465;margin-bottom:4px;">Refresh</div>
                <div style="font-size:15px;line-height:1.35;color:#2f241d;font-weight:700;">{_email_escape(refresh_text)}</div>
              </td>
            </tr>
          </table>
        </div>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;margin:0 0 18px;">
          <tr>
            <td style="width:50%;padding:0 8px 8px 0;">
              <div style="border-radius:14px;background:#f7eee3;padding:14px 16px;border:1px solid #ecd8c3;min-height:96px;">
                <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#8a7465;">Selected</div>
                <div style="font-size:28px;line-height:1.05;color:#2f241d;font-weight:700;">{len(candidates)}</div>
                <div style="font-size:12px;line-height:1.35;color:#5a4a3e;margin-top:6px;">Kept picks</div>
              </div>
            </td>
            <td style="width:50%;padding:0 0 8px 8px;">
              <div style="border-radius:14px;background:#f4e7dc;padding:14px 16px;border:1px solid #ecd8c3;min-height:96px;">
                <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#8a7465;">Read First</div>
                <div style="font-size:28px;line-height:1.05;color:#8f4b2e;font-weight:700;">{read_first_count}</div>
                <div style="font-size:12px;line-height:1.35;color:#5a4a3e;margin-top:6px;">Start here</div>
              </div>
            </td>
          </tr>
          <tr>
            <td style="width:50%;padding:8px 8px 0 0;">
              <div style="border-radius:14px;background:#f5f3ec;padding:14px 16px;border:1px solid #e2ddd2;min-height:96px;">
                <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#8a7465;">Skim</div>
                <div style="font-size:28px;line-height:1.05;color:#6a664e;font-weight:700;">{skim_count}</div>
                <div style="font-size:12px;line-height:1.35;color:#5a4a3e;margin-top:6px;">Fast scan</div>
              </div>
            </td>
            <td style="width:50%;padding:8px 0 0 8px;">
              <div style="border-radius:14px;background:#faf5ee;padding:14px 16px;border:1px solid #ecd8c3;min-height:96px;">
                <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#8a7465;">Themes</div>
                <div style="font-size:28px;line-height:1.05;color:#2f241d;font-weight:700;">{len(themes) if themes else 0}</div>
                <div style="font-size:12px;line-height:1.35;color:#5a4a3e;margin-top:6px;">Map lanes</div>
              </div>
            </td>
          </tr>
        </table>
        <div style="border-left:3px solid #bd6a42;padding-left:14px;margin:0 0 18px;">
          <div style="font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:#8f4b2e;font-weight:700;margin-bottom:6px;">Lead paper</div>
          <div style="font-size:20px;line-height:1.25;color:#2f241d;font-weight:700;margin-bottom:6px;">{_email_escape(lead_title)}</div>
          <div style="font-size:14px;line-height:1.6;color:#5a4a3e;">{_email_escape(lead_reason or 'Open the attached HTML digest for the full reading cards and rationale.')}</div>
        </div>
        <div style="font-size:14px;line-height:1.65;color:#5a4a3e;margin-bottom:8px;">Themes touched in this batch: {_email_escape(theme_line)}.</div>
        <div style="font-size:14px;line-height:1.65;color:#5a4a3e;">Attachment: <strong>{_email_escape(html_path.name)}</strong>. Open it in a browser for the full styled digest.</div>
      </div>
    </div>
  </body>
</html>"""
    return plain, html


def _format_search_email_body(*, query: str, papers: list[dict], date_str: str, html_path: Path) -> tuple[str, str]:
    top_title = str(papers[0].get("title") or "Search results attached").strip() if papers else "Search results attached"
    short_date = _display_date(date_str)
    plain = "\n".join(
        [
            f"Search Results | {short_date}",
            "",
            f"Query: {query}",
            f"Results: {len(papers)}",
            f"Top hit: {top_title}",
            "",
            f"Attachment: {html_path.name}",
            "Open the attached HTML file in a browser for the full styled results.",
        ]
    )
    html = f"""\
<html>
  <body style="margin:0;padding:0;background:#f6ede1;color:#2f241d;font-family:Arial,'Helvetica Neue',sans-serif;">
    <div style="max-width:640px;margin:0 auto;padding:24px 18px;">
      <div style="background:#fffaf3;border:1px solid #e6d6c4;border-radius:18px;padding:24px 22px;">
        <div style="font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:#8f4b2e;font-weight:700;margin-bottom:12px;">Research Assist Search</div>
        <h1 style="margin:0 0 10px;font-size:30px;line-height:1.1;color:#2f241d;">Search results are ready</h1>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#5a4a3e;">Query: <strong>{_email_escape(query)}</strong></p>
        <p style="margin:0 0 10px;font-size:14px;line-height:1.65;color:#5a4a3e;">Found <strong>{len(papers)}</strong> results. Top hit: <strong>{_email_escape(top_title)}</strong>.</p>
        <p style="margin:0;font-size:14px;line-height:1.65;color:#5a4a3e;">Attachment: <strong>{_email_escape(html_path.name)}</strong>. Open it in a browser for the full styled results.</p>
      </div>
    </div>
  </body>
</html>"""
    return plain, html


def _send_email_delivery(
    *,
    config: dict,
    subject: str,
    body_text: str,
    body_html: str | None,
    html_path: Path,
    output_json_path: Path | None,
    extra_attachments: list[Path] | None = None,
) -> tuple[str, Path | None]:
    if not _email_send_enabled(config):
        return "disabled by config", None

    email_cfg = _email_config(config)
    attachments = []
    if _config_bool(email_cfg.get("attach_html", True), True):
        attachments.append(html_path)
    if extra_attachments:
        attachments.extend(extra_attachments)

    result = send_email(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        sender=str(email_cfg.get("sender", "")).strip(),
        recipients=email_cfg.get("recipients", []),
        smtp_server=str(email_cfg.get("smtp_server", "")).strip(),
        smtp_port=int(email_cfg.get("smtp_port", 465)),
        smtp_user=str(email_cfg.get("smtp_user", "")).strip(),
        smtp_pass=str(email_cfg.get("smtp_pass", "")).strip(),
        tls_mode=str(email_cfg.get("tls_mode", "ssl")).strip(),
        timeout=int(email_cfg.get("timeout", 20)),
        attachments=attachments,
    )

    email_json_path = None
    if output_json_path is not None and _email_write_metadata(config):
        metadata = {
            "subject": result["subject"],
            "sender": result["sender"],
            "recipients": result["recipients"],
            "attachments": result["attachments"],
        }
        output_json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        email_json_path = output_json_path

    return "sent ✓", email_json_path


def _send_telegram_delivery(
    *,
    config: dict,
    summary_text: str,
    html_path: Path,
    output_json_path: Path | None,
) -> tuple[str, Path | None]:
    if not _telegram_send_enabled(config):
        return "disabled by config", None

    telegram_json_path = None
    if output_json_path is not None:
        output_json_path.write_text(
            json.dumps(
                {
                    "summary": summary_text,
                    "html_path": html_path.as_posix(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        telegram_json_path = output_json_path

    send_digest(summary_text, html_path)
    return "sent ✓", telegram_json_path


def _deliver_report(
    *,
    config: dict,
    preferred_channel: str,
    subject: str,
    summary_text: str,
    email_body_text: str,
    email_body_html: str | None,
    html_path: Path,
    email_json_path: Path | None,
    telegram_json_path: Path | None,
    extra_email_attachments: list[Path] | None = None,
) -> tuple[str, Path | None, str, Path | None]:
    email_status = "not attempted"
    telegram_status = "not attempted"
    final_email_json_path = None
    final_telegram_json_path = None

    if preferred_channel == "telegram":
        try:
            telegram_status, final_telegram_json_path = _send_telegram_delivery(
                config=config,
                summary_text=summary_text,
                html_path=html_path,
                output_json_path=telegram_json_path,
            )
        except Exception as exc:
            LOG.warning("Failed to send via Telegram: %s", exc)
            telegram_status = f"failed — {exc}"
        if telegram_status == "disabled by config" and _email_send_enabled(config):
            try:
                email_status, final_email_json_path = _send_email_delivery(
                    config=config,
                    subject=subject,
                    body_text=email_body_text,
                    body_html=email_body_html,
                    html_path=html_path,
                    output_json_path=email_json_path,
                    extra_attachments=extra_email_attachments,
                )
            except Exception as exc:
                LOG.warning("Failed to send via email: %s", exc)
                email_status = f"failed — {exc}"
        return email_status, final_email_json_path, telegram_status, final_telegram_json_path

    try:
        email_status, final_email_json_path = _send_email_delivery(
            config=config,
            subject=subject,
            body_text=email_body_text,
            body_html=email_body_html,
            html_path=html_path,
            output_json_path=email_json_path,
            extra_attachments=extra_email_attachments,
        )
    except Exception as exc:
        LOG.warning("Failed to send via email: %s", exc)
        email_status = f"failed — {exc}"

    should_fallback = (email_status.startswith("failed") and _telegram_fallback_on_failure(config)) or (
        email_status == "disabled by config" and _telegram_send_enabled(config)
    )
    should_use_telegram_primary = preferred_channel == "telegram"
    if should_use_telegram_primary or should_fallback:
        try:
            telegram_status, final_telegram_json_path = _send_telegram_delivery(
                config=config,
                summary_text=summary_text,
                html_path=html_path,
                output_json_path=telegram_json_path,
            )
        except Exception as exc:
            LOG.warning("Failed to send via Telegram: %s", exc)
            telegram_status = f"failed — {exc}"
    else:
        if _telegram_send_enabled(config):
            telegram_status = "backup not used"
        else:
            telegram_status = "disabled by config"

    return email_status, final_email_json_path, telegram_status, final_telegram_json_path


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def expand_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def get_profile_path(config: dict) -> Path:
    profile_path_str = config.get("profile_path", "~/.claude/tools/paper-finder/profiles/research-interest.json")
    return expand_path(profile_path_str)


def get_output_root(config: dict) -> Path:
    output_root_str = config.get("output_root", "~/.claude/tools/paper-finder/reports")
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


def _load_candidates_from_digest(digest_json_path: Path) -> list[dict]:
    digest_data = json.loads(digest_json_path.read_text(encoding="utf-8"))
    candidate_paths = digest_data.get("candidate_paths", [])
    candidates = []
    for candidate_path in candidate_paths:
        try:
            candidate_data = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
            candidates.append(candidate_data)
        except Exception as exc:
            LOG.warning("Failed to load candidate %s: %s", candidate_path, exc)
    return candidates


def _digest_date_str(candidates: list[dict]) -> str:
    for candidate in candidates:
        generated_at = str(candidate.get("candidate", {}).get("generated_at") or "").strip()
        if len(generated_at) >= 10:
            return generated_at[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _nearest_zotero_lines(candidate: dict) -> list[str]:
    scores = candidate.get("_scores", {})
    review = candidate.get("review", {})
    neighbors = scores.get("semantic_neighbors") if isinstance(scores, dict) else None
    titles: list[str] = []
    if isinstance(neighbors, list) and neighbors:
        cleaned = [str(item.get("title") or "").strip() for item in neighbors if isinstance(item, dict)]
        cleaned = [title for title in cleaned if title]
        if len(cleaned) >= 2 and len(cleaned[0]) + len(cleaned[1]) <= 72:
            titles = cleaned[:2]
        elif cleaned:
            titles = cleaned[:1]
    if not titles:
        top_title = str((scores or {}).get("semantic_top_title") or "").strip()
        if top_title:
            titles = [top_title]
    if not titles and isinstance(review, dict):
        zotero_comparison = review.get("zotero_comparison")
        if isinstance(zotero_comparison, dict):
            related_items = zotero_comparison.get("related_items")
            if isinstance(related_items, list):
                cleaned = [str(item.get("title") or "").strip() for item in related_items if isinstance(item, dict)]
                cleaned = [title for title in cleaned if title]
                if len(cleaned) >= 2 and len(cleaned[0]) + len(cleaned[1]) <= 72:
                    titles = cleaned[:2]
                elif cleaned:
                    titles = cleaned[:1]
            summary = str(zotero_comparison.get("summary") or "").strip()
            if titles:
                return [f"**Nearest Zotero:** {'; '.join(titles)}"]
            if summary:
                return [f"**Nearest Zotero:** {summary}"]
    if titles:
        return [f"**Nearest Zotero:** {'; '.join(titles)}"]
    return []


def _candidate_json_paths(candidates: list[dict]) -> list[Path]:
    paths: list[Path] = []
    for candidate in candidates:
        json_path = candidate.get("candidate", {}).get("json_path")
        if isinstance(json_path, str) and json_path:
            paths.append(Path(json_path).expanduser().resolve())
    return paths


def _persist_ranked_candidate_paths(digest_json_path: Path, candidates: list[dict]) -> None:
    payload = json.loads(digest_json_path.read_text(encoding="utf-8"))
    payload.setdefault("retrieved_candidate_count", payload.get("candidate_count"))
    payload["selected_candidate_count"] = len(candidates)
    payload["candidate_paths"] = [path.as_posix() for path in _candidate_json_paths(candidates)]
    digest_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _selected_candidate_limit(config: dict) -> int | None:
    review_cfg = config.get("review_generation", {})
    if not isinstance(review_cfg, dict):
        return None
    value = review_cfg.get("agent_top_n")
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        limit = int(value.strip())
        if limit > 0:
            return limit
    return None


def _final_digest_limit(config: dict) -> int | None:
    review_cfg = config.get("review_generation", {})
    if not isinstance(review_cfg, dict):
        return 5
    value = review_cfg.get("final_top_n", 5)
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        limit = int(value.strip())
        if limit > 0:
            return limit
    return 5


def _filter_final_digest_candidates(candidates: list[dict], *, final_limit: int | None) -> list[dict]:
    selected = [
        candidate
        for candidate in candidates
        if isinstance(candidate.get("review"), dict) and candidate["review"].get("selected_for_digest") is True
    ]
    if selected:
        if final_limit is not None and len(selected) > final_limit:
            return selected[:final_limit]
        return selected
    return candidates


def _render_digest_outputs(
    digest_json_path: Path,
    candidates: list[dict],
    output_root: Path,
    fmt: str,
    config: dict,
    *,
    action_name: str,
    profile_path: Path | None,
) -> str:
    date_str = _digest_date_str(candidates)

    html_content = format_digest_html(candidates, date_str)
    html_path = output_root / f"digest-{date_str}.html"
    html_path.write_text(html_content, encoding="utf-8")
    LOG.info("Wrote HTML digest to %s", html_path)

    email_json_path: Path | None = None
    telegram_json_path: Path | None = None

    if fmt in {"telegram", "delivery"}:
        telegram_summary = format_digest_telegram(candidates, date_str)
        profile_summary = _load_profile_summary(profile_path, config)
        email_body_text, email_body_html = _format_digest_email_body(
            candidates,
            date_str=date_str,
            html_path=html_path,
            profile_summary=profile_summary,
        )
        email_json_path = output_root / f"digest-{date_str}.email.json"
        telegram_json_path = output_root / f"digest-{date_str}.telegram.json"
        email_status, email_json_path, telegram_status, telegram_json_path = _deliver_report(
            config=config,
            preferred_channel=_primary_delivery_channel(config),
            subject=_digest_email_subject(config, date_str=date_str, candidates=candidates),
            summary_text=telegram_summary,
            email_body_text=email_body_text,
            email_body_html=email_body_html,
            html_path=html_path,
            email_json_path=email_json_path,
            telegram_json_path=telegram_json_path,
            extra_email_attachments=[digest_json_path] if _config_bool(_email_config(config).get("attach_digest_json", False), False) else None,
        )

        lines = [f"Found {len(candidates)} papers, top 5:"]
        for i, candidate in enumerate(candidates[:5], 1):
            paper = candidate.get("paper", {})
            title = paper.get("title", "Untitled")
            arxiv_id = paper.get("identifiers", {}).get("arxiv_id", "")
            scores = candidate.get("_scores", {})
            score = scores.get("total", 0.0)
            lines.append(f"{i}. [{score:.2f}] {title[:60]}... ({arxiv_id})")
        file_names = [html_path.name]
        if email_json_path is not None:
            file_names.append(email_json_path.name)
        if telegram_json_path is not None:
            file_names.append(telegram_json_path.name)
        lines.append(f"Files: {', '.join(file_names)}")
        summary_path = write_digest_run_summary(
            action=action_name,
            digest_json_path=digest_json_path,
            candidate_paths=_candidate_json_paths(candidates),
            html_path=html_path,
            email_json_path=email_json_path,
            telegram_json_path=telegram_json_path,
            output_root=output_root,
            profile_path=profile_path,
        )
        lines.append(f"Summary: {summary_path.name}")
        lines.append(f"Primary channel: {_primary_delivery_channel(config)}")
        lines.append(f"Email: {email_status}")
        lines.append(f"Telegram: {telegram_status}")
        return "\n".join(lines)

    summary_path = write_digest_run_summary(
        action=action_name,
        digest_json_path=digest_json_path,
        candidate_paths=_candidate_json_paths(candidates),
        html_path=html_path,
        email_json_path=None,
        telegram_json_path=None,
        output_root=output_root,
        profile_path=profile_path,
    )
    LOG.info("Wrote digest run summary to %s", summary_path)
    return format_digest_markdown(digest_json_path, candidates)


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
        review = candidate.get("review", {})
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
            lines.append(
                f"**Score:** {scores['total']:.2f} "
                f"(map={scores.get('map_match', 0.0):.2f} zotero={scores.get('zotero_semantic', 0.0):.2f})"
            )
        if review.get("recommendation"):
            lines.append(f"**Recommendation:** {review['recommendation']}")
        if review.get("why_it_matters"):
            lines.append(f"**Why It Matters:** {review['why_it_matters']}")
        if review.get("quick_takeaways"):
            lines.append(f"**Quick Takeaways:** {'; '.join(review['quick_takeaways'])}")
        if review.get("caveats"):
            lines.append(f"**Caveats:** {'; '.join(review['caveats'])}")
        lines.extend(_nearest_zotero_lines(candidate))
        if abstract:
            abstract_preview = abstract[:300] + ("..." if len(abstract) > 300 else "")
            lines.append(f"\n**Original arXiv Abstract:** {abstract_preview}")
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
            lines.append(f"\n**Original arXiv Abstract:** {abstract_preview}")
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
        lines.append("Use the OpenClaw controller or agent workflow to regenerate the live profile from Zotero evidence.")
    else:
        lines.append("The profile is up to date.")
    return "\n".join(lines)


def action_digest(config: dict, fmt: str = "markdown", *, config_path: Path | None = None) -> str:
    profile_path = get_profile_path(config)
    output_root = get_output_root(config)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    temp_toml_path = create_temp_toml_config(config, profile_path, output_root)
    profile: dict | None = None

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

        candidates = _load_candidates_from_digest(digest_json_path)

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
            semantic_search_fn = None
            if config_path is not None and _semantic_search_enabled(config):
                try:
                    semantic_search = create_semantic_search(config_path=config_path)

                    def _search(query_text: str, limit: int) -> dict:
                        return semantic_search.search(query=query_text, limit=limit)

                    semantic_search_fn = _search
                except Exception as exc:
                    LOG.warning("Semantic ranking unavailable: %s", exc)

            candidates = rank_candidates(
                candidates,
                profile,
                history_ids,
                semantic_search_fn=semantic_search_fn,
            )
            LOG.info("Ranked %d candidates", len(candidates))

        selected_limit = _selected_candidate_limit(config)
        if selected_limit is not None and len(candidates) > selected_limit:
            candidates = candidates[:selected_limit]
            LOG.info("Trimmed ranked candidates to top %d", len(candidates))

        if candidates and _review_fallback_to_system(config):
            candidates = enrich_candidates_with_system_review(candidates, profile, persist_json=True)
            LOG.info("Enriched %d candidates with system review notes", len(candidates))
        if candidates:
            _persist_ranked_candidate_paths(digest_json_path, candidates)
        return _render_digest_outputs(
            digest_json_path,
            candidates,
            output_root,
            fmt,
            config,
            action_name="digest",
            profile_path=profile_path,
        )
    finally:
        try:
            temp_toml_path.unlink()
        except Exception:
            pass


def action_search(query: str, top: int = 5, fmt: str = "markdown", config: dict | None = None, config_path: Path | None = None, source: str = "openalex") -> str:
    config = config or {}

    # Use OpenAlex search (default, no journal restriction)
    if source == "openalex" or source == "all":
        LOG.info("Searching OpenAlex (all sources) for: %s", query)
        try:
            from .openalex_pipeline.client import search_works
            papers = search_works(keywords=[query], per_page=top, sort="relevance_score:desc")
            LOG.info("Found %d results from OpenAlex", len(papers))

            lines = [f"# OpenAlex Search: \"{query}\"", f"\nFound {len(papers)} results:\n"]
            for i, paper in enumerate(papers, 1):
                title = paper.get("title", "Untitled")
                authors = ", ".join([a["name"] for a in paper.get("authors", [])[:3]])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."
                source_name = paper.get("_source", "Unknown")
                date = paper.get("publication_date", "")
                cited = paper.get("cited_by_count", 0)
                url = paper.get("url", "")
                abstract = paper.get("abstract", "")[:300] + "..." if len(paper.get("abstract", "")) > 300 else paper.get("abstract", "")

                lines.append(f"## {i}. {title}")
                if authors:
                    lines.append(f"**Authors:** {authors}")
                if source_name:
                    lines.append(f"**Source:** {source_name}")
                if date:
                    lines.append(f"**Date:** {date}")
                if cited:
                    lines.append(f"**Cited:** {cited}")
                if url:
                    lines.append(f"**URL:** {url}")
                if abstract:
                    lines.append(f"\n> {abstract}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            LOG.warning("OpenAlex search failed: %s", exc)

    # NBER search
    if source == "nber":
        LOG.info("Searching NBER for: %s", query)
        try:
            from .openalex_pipeline.client import search_and_parse
            papers = search_and_parse(keywords=[query], per_page=top)
            LOG.info("Found %d results from NBER", len(papers))

            lines = [f"# NBER Search: \"{query}\"", f"\nFound {len(papers)} results:\n"]
            for i, paper in enumerate(papers, 1):
                title = paper.get("title", "Untitled")
                authors = ", ".join([a["name"] for a in paper.get("authors", [])[:3]])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."
                nber_id = paper.get("nber_id", "")
                date = paper.get("publication_date", "")
                cited = paper.get("cited_by_count", 0)
                url = paper.get("url", "")
                abstract = paper.get("abstract", "")[:300] + "..." if len(paper.get("abstract", "")) > 300 else paper.get("abstract", "")

                lines.append(f"## {i}. {title}")
                if authors:
                    lines.append(f"**Authors:** {authors}")
                if nber_id:
                    lines.append(f"**NBER:** {nber_id}")
                if date:
                    lines.append(f"**Date:** {date}")
                if cited:
                    lines.append(f"**Cited:** {cited}")
                if url:
                    lines.append(f"**URL:** {url}")
                if abstract:
                    lines.append(f"\n> {abstract}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            LOG.warning("NBER search failed: %s", exc)

    # Journal search (e.g., JPE, AER, etc.)
    if source.upper() in JOURNAL_ALIAS:
        journal_id = JOURNAL_ALIAS[source.upper()]
        LOG.info("Searching %s for: %s", source, query)
        try:
            from .openalex_pipeline.client import search_journal_papers
            papers = search_journal_papers(source_id=journal_id, keywords=[query], per_page=top)
            LOG.info("Found %d results from %s", len(papers), source)

            lines = [f"# {source} Search: \"{query}\"", f"\nFound {len(papers)} results:\n"]
            for i, paper in enumerate(papers, 1):
                title = paper.get("title", "Untitled")
                authors = ", ".join([a["name"] for a in paper.get("authors", [])[:3]])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."
                date = paper.get("publication_date", "")
                cited = paper.get("cited_by_count", 0)
                url = paper.get("url", "")
                abstract = paper.get("abstract", "")[:300] + "..." if len(paper.get("abstract", "")) > 300 else paper.get("abstract", "")

                lines.append(f"## {i}. {title}")
                if authors:
                    lines.append(f"**Authors:** {authors}")
                if date:
                    lines.append(f"**Date:** {date}")
                if cited:
                    lines.append(f"**Cited:** {cited}")
                if url:
                    lines.append(f"**URL:** {url}")
                if abstract:
                    lines.append(f"\n> {abstract}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            LOG.warning("%s search failed: %s", source, exc)

    # Use Zotero semantic search if enabled
    if source == "zotero" and _semantic_search_enabled(config) and config_path is not None:
        LOG.info("Searching Zotero library for: %s", query)
        try:
            semantic_search = create_semantic_search(config_path=config_path)
            result = semantic_search.search(query=query, limit=top)
            items = result.get("results", [])
            LOG.info("Found %d results in Zotero library", len(items))
            lines = [f"# Zotero Library Search: \"{query}\"", f"\nFound {len(items)} results:\n"]
            for i, item in enumerate(items, 1):
                meta = item.get("metadata") or {}
                title = meta.get("title") or item.get("item_key", "Unknown")
                creators = meta.get("creators") or meta.get("author") or ""
                year = meta.get("date") or meta.get("year") or ""
                score = item.get("similarity_score")
                score_str = f" (similarity: {score:.2f})" if score is not None else ""
                abstract = meta.get("abstract") or item.get("matched_text") or ""
                abstract_preview = abstract[:200] + "..." if len(abstract) > 200 else abstract
                lines.append(f"## {i}. {title}")
                if creators:
                    lines.append(f"**Authors:** {creators}")
                if year:
                    lines.append(f"**Year:** {year}{score_str}")
                elif score_str:
                    lines.append(f"**Score:**{score_str}")
                if abstract_preview:
                    lines.append(f"\n{abstract_preview}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            LOG.warning("Semantic search failed, falling back to arXiv: %s", exc)

    LOG.info("Searching arXiv for: %s", query)
    search_query = build_search_query(categories=[], keywords=[query], exclude_keywords=None, logic="OR")
    xml_text = fetch_arxiv_feed(search_query, start=0, max_results=top, sort_by="relevance", sort_order="descending")
    papers = parse_feed(xml_text)
    LOG.info("Found %d results", len(papers))

    papers_subset = papers[:top]

    if fmt in {"telegram", "delivery"}:
        telegram_summary = format_search_telegram(papers_subset, query)
        html_content = format_search_html(papers_subset, query)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        search_output_dir = Path.home() / ".claude" / "tools" / "paper-finder" / "reports" / "search"
        search_output_dir.mkdir(parents=True, exist_ok=True)

        html_path = search_output_dir / f"search-{date_str}.html"
        html_path.write_text(html_content, encoding="utf-8")
        LOG.info("Wrote HTML search results to %s", html_path)

        telegram_json_path = search_output_dir / f"search-{date_str}.telegram.json"
        email_json_path = search_output_dir / f"search-{date_str}.email.json"
        email_body_text, email_body_html = _format_search_email_body(query=query, papers=papers_subset, date_str=date_str, html_path=html_path)
        email_status, email_json_path, telegram_status, telegram_json_path = _deliver_report(
            config=config or {},
            preferred_channel=_primary_delivery_channel(config or {}),
            subject=_search_email_subject(config or {}, date_str=date_str, query=query, paper_count=len(papers_subset)),
            summary_text=format_search_markdown(papers_subset, query),
            email_body_text=email_body_text,
            email_body_html=email_body_html,
            html_path=html_path,
            email_json_path=email_json_path,
            telegram_json_path=telegram_json_path,
            extra_email_attachments=None,
        )

        lines = [f"Found {len(papers_subset)} results for \"{query}\":"]
        for i, paper in enumerate(papers_subset, 1):
            title = paper.get("title", "Untitled")
            arxiv_id = paper.get("arxiv_id", "")
            lines.append(f"{i}. {title[:60]}... ({arxiv_id})")
        file_names = [html_path.name]
        if email_json_path is not None:
            file_names.append(email_json_path.name)
        if telegram_json_path is not None:
            file_names.append(telegram_json_path.name)
        lines.append(f"Files: {', '.join(file_names)}")
        lines.append(f"Primary channel: {_primary_delivery_channel(config or {})}")
        lines.append(f"Email: {email_status}")
        lines.append(f"Telegram: {telegram_status}")
        return "\n".join(lines)

    return format_search_markdown(papers_subset, query)


def action_render_digest(config: dict, digest_json: Path, fmt: str = "markdown") -> str:
    output_root = get_output_root(config)
    output_root.mkdir(parents=True, exist_ok=True)
    digest_json_path = digest_json.expanduser().resolve()
    candidates = _load_candidates_from_digest(digest_json_path)
    candidates = _filter_final_digest_candidates(candidates, final_limit=_final_digest_limit(config))
    profile_path = get_profile_path(config)
    return _render_digest_outputs(
        digest_json_path,
        candidates,
        output_root,
        fmt,
        config,
        action_name="render-digest",
        profile_path=profile_path,
    )


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


def action_sync_index(config: dict, *, config_path: Path | None = None, force_rebuild: bool = False) -> str:
    """Sync Zotero items into the semantic search index via API."""
    LOG.info("Syncing Zotero items into semantic search index via API...")
    if not _semantic_search_enabled(config):
        return "Semantic search is disabled in config. Set semantic_search.enabled=true first."
    try:
        semantic_search = create_semantic_search(config_path=config_path)
    except Exception as exc:
        return f"Failed to initialize semantic search: {exc}"

    zotero_cfg = config.get("zotero", {})
    scope = str(zotero_cfg.get("scope_collection") or "").strip()
    collection_names = [scope] if scope else None

    result = semantic_search.sync_from_api(
        collection_names=collection_names,
        force_rebuild=force_rebuild,
    )
    lines = [
        "Sync complete",
        f"  Source: {result.get('source', 'api')}",
        f"  Items fetched: {result.get('total_items', 0)}",
        f"  Items indexed: {result.get('processed_items', 0)}",
        f"  Scope: {', '.join(result.get('scope_collections', ['all']))}",
        f"  Embedding model: {result.get('embedding_model', 'unknown')}",
    ]
    return "\n".join(lines)


def action_digest_nber(config: dict, fmt: str = "markdown", *, config_path: Path | None = None) -> str:
    """Generate digest from NBER working papers."""
    profile_path = get_profile_path(config)
    output_root = get_output_root(config)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    LOG.info("Running NBER retrieval pipeline...")
    result = run_nber_pipeline(config_path=config_path or Path.cwd() / "config.json", profile_path=profile_path, write_candidate_markdown_override=None)

    digest_json_path = Path(result["digest_json_path"])
    candidate_count = result["candidate_count"]
    LOG.info("Retrieved %d NBER candidates", candidate_count)

    # Load candidates and rank them
    candidates = _load_candidates_from_digest(digest_json_path)

    # Load profile for ranking
    profile = load_config(profile_path)

    # Setup semantic search for ranking
    semantic_search_fn = None
    if config_path is not None and _semantic_search_enabled(config):
        try:
            semantic_search = create_semantic_search(config_path=config_path)

            def _search(query_text: str, limit: int) -> dict:
                return semantic_search.search(query=query_text, limit=limit)

            semantic_search_fn = _search
        except Exception as exc:
            LOG.warning("Semantic ranking unavailable: %s", exc)

    # Rank candidates
    candidates = rank_candidates(
        candidates,
        profile,
        semantic_search_fn=semantic_search_fn,
    )
    LOG.info("Ranked %d NBER candidates", len(candidates))

    # Save ranked candidates back to JSON with scores
    output_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Import markdown generator
    from .nber_pipeline.pipeline import _generate_candidate_markdown

    for candidate in candidates:
        nber_id = candidate.get("paper", {}).get("identifiers", {}).get("nber_id", "")
        if nber_id:
            # Find the JSON file
            for existing_path in output_root.glob(f"*{nber_id}.json"):
                try:
                    existing = json.loads(existing_path.read_text(encoding="utf-8"))
                    existing["_scores"] = candidate.get("_scores", {})
                    existing["candidate"]["interest_name"] = candidate.get("candidate", {}).get("interest_name", "")
                    existing_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

                    # Also regenerate markdown with scores
                    md_path = existing_path.with_suffix('.md')
                    md_content = _generate_candidate_markdown(existing)
                    md_path.write_text(md_content, encoding="utf-8")

                    LOG.info("Updated scores for %s", nber_id)
                except Exception as exc:
                    LOG.warning("Failed to update JSON %s: %s", existing_path, exc)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if fmt in {"telegram", "delivery"}:
        # Simple HTML for NBER
        from .html_fmt import format_digest_html
        html_content = format_digest_html(candidates, date_str)
        html_path = output_root / f"nber-digest-{date_str}.html"
        html_path.write_text(html_content, encoding="utf-8")

        telegram_summary = format_digest_telegram(candidates, date_str)

        lines = [
            f"Found {len(candidates)} NBER working papers",
            "",
            f"HTML: {html_path}",
        ]
        for i, candidate in enumerate(candidates[:5], 1):
            paper = candidate.get("paper", {})
            title = paper.get("title", "Untitled")
            nber_id = paper.get("identifiers", {}).get("nber_id", "")
            lines.append(f"{i}. {title[:60]}... ({nber_id})")
        return "\n".join(lines)

    # Markdown format
    lines = [f"# NBER Working Papers Digest {date_str}", ""]
    lines.append(f"Found {len(candidates)} new papers:")
    lines.append("")

    for i, candidate in enumerate(candidates, 1):
        paper = candidate.get("paper", {})
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", [])
        nber_id = paper.get("identifiers", {}).get("nber_id", "")
        url = paper.get("identifiers", {}).get("url", "")
        abstract = paper.get("abstract", "")
        triage = candidate.get("triage", {})
        matched_interests = triage.get("matched_interest_labels", [])

        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        lines.append(f"## {i}. {title}")
        if author_str:
            lines.append(f"**Authors:** {author_str}")
        if nber_id:
            lines.append(f"**NBER ID:** {nber_id}")
        if url:
            lines.append(f"**URL:** {url}")
        if matched_interests:
            lines.append(f"**Matched Interests:** {', '.join(matched_interests)}")
        if abstract:
            abstract_preview = abstract[:300] + ("..." if len(abstract) > 300 else "")
            lines.append(f"\n**Abstract:** {abstract_preview}")
        lines.append("")

    lines.append("---")
    lines.append(f"Full digest: {digest_json_path.as_posix()}")
    return "\n".join(lines)


def generate_llm_insights(papers: list[dict], profile: dict) -> dict[int, str]:
    """Generate LLM insights for high-relevance papers using DashScope API.

    Returns:
        Dict mapping paper index (1-based) to insight text.
    """
    if not papers:
        return {}

    # Build interest context
    interest_lines = []
    for interest in profile.get("interests", []):
        name = interest.get("label", "")
        keywords = interest.get("method_keywords", [])
        aliases = interest.get("query_aliases", [])
        interest_lines.append(f"- {name}: 关键词 {keywords}, 别名 {aliases}")

    interests_context = "\n".join(interest_lines)

    # Build papers context (title + abstract for each)
    papers_context = []
    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")[:800]
        papers_context.append(f"{i}. {title}\n   摘要: {abstract}")

    papers_text = "\n\n".join(papers_context)

    # Call DashScope API
    api_key = os.getenv("DASHSCOPE_API_KEY") or "sk-b060ce4b157c403eb727c99a780ab19c"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    system_prompt = """你是一位经济学研究助手，帮助用户理解论文与其研究兴趣的相关性。
用户的研究兴趣包括：公共财政、住房政策、地方财政、城市经济学、中国经济。
请用中文输出，对每篇论文用2-3句话说明为什么这篇论文可能引起用户兴趣。
格式要求：输出N段文字，每段对应一篇论文，直接开始正文，不要加编号或标题。"""

    user_prompt = f"""用户的研究兴趣：
{interests_context}

需要分析的论文（共{len(papers)}篇）：
{papers_text}

请按顺序输出每篇论文的分析，每段对应一篇论文。"""

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "qwen-plus",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse content into dict by splitting on double newlines
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        insights = {}
        for i, para in enumerate(paragraphs, 1):
            if i <= len(papers):
                insights[i] = para

        LOG.info("LLM analysis completed: %d insights generated", len(insights))
        return insights
    except Exception as e:
        LOG.warning("LLM API call failed: %s", e)
        return {}


def action_digest_all(config: dict, fmt: str = "markdown", *, config_path: Path | None = None) -> str:
    """Generate digest from all sources: NBER + 17 journals.

    Uses the interest profile to score and rank papers by relevance.
    Saves result to vault and prints to stdout.
    """
    from .openalex_pipeline.client import search_journal_papers, search_and_parse
    from .ranker import score_map_match

    profile_path = get_profile_path(config)
    profile = load_config(profile_path)
    interests = profile.get("interests", [])

    if not interests:
        return "No interests found in profile. Please run profile-refresh first."

    LOG.info("Running digest-all for %d interests across NBER + %d journals", len(interests), len(JOURNAL_ALIAS))

    all_candidates = []
    per_source_limit = 10

    # First: NBER
    LOG.info("Searching NBER...")
    try:
        nber_papers = search_and_parse(per_page=per_source_limit)
        for paper in nber_papers:
            paper["_source"] = "NBER"
            paper["_source_id"] = NBER_REPO_ID
        all_candidates.extend(nber_papers)
        LOG.info("Found %d NBER papers", len(nber_papers))
    except Exception as e:
        LOG.warning("Failed to search NBER: %s", e)

    # Then: each journal
    for journal_name, journal_id in JOURNAL_ALIAS.items():
        LOG.info("Searching %s...", journal_name)
        try:
            # Build search query from interest keywords
            search_keywords = []
            for interest in interests:
                keywords = interest.get("keywords", [])
                search_keywords.extend(keywords[:2])  # Take top 2 keywords per interest
            search_keywords = list(set(search_keywords))[:5]  # Unique, max 5

            papers = search_journal_papers(source_id=journal_id, keywords=search_keywords, per_page=per_source_limit)
            for paper in papers:
                paper["_source"] = journal_name
                paper["_source_id"] = journal_id
            all_candidates.extend(papers)
            LOG.info("Found %d papers from %s", len(papers), journal_name)
        except Exception as e:
            LOG.warning("Failed to search %s: %s", journal_name, e)

    # Score by relevance to interests
    LOG.info("Scoring papers by relevance...")
    for paper in all_candidates:
        # Wrap in candidate format for score_map_match
        candidate = {"paper": paper}
        relevance_score = score_map_match(candidate, profile)
        paper["_relevance"] = relevance_score

    # Sort by relevance (descending), then by citations
    all_candidates.sort(key=lambda x: (x.get("_relevance", 0), x.get("cited_by_count", 0)), reverse=True)
    top_candidates = all_candidates[:50]  # Top 50 by relevance

    # LLM analysis for high-relevance papers (> 0.8)
    LOG.info("Running LLM analysis for high-relevance papers...")
    high_relevance_papers = [p for p in top_candidates if p.get("_relevance", 0) > 0.8]
    llm_insights = {}
    if high_relevance_papers:
        try:
            llm_insights = generate_llm_insights(high_relevance_papers, profile)
        except Exception as e:
            LOG.warning("LLM analysis failed: %s", e)

    # Build index mapping for high-relevance papers in top_candidates
    high_paper_ids = {id(p): idx + 1 for idx, p in enumerate(high_relevance_papers)}

    # Generate output
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        "---",
        f"title: \"Literature Digest - {date_str}\"",
        "tags: [digest, literature]",
        f"created: {date_str}",
        "---",
        "",
        f"# Literature Digest (All Sources) - {date_str}",
        "",
        f"> Sources: NBER + {len(JOURNAL_ALIAS)} journals",
        f"> Interests: {', '.join(i.get('name', '') for i in interests)}",
        f"> Total found: {len(all_candidates)} papers",
        f"> Sorted by: Relevance score",
        "",
        "---",
        ""
    ]

    for i, paper in enumerate(top_candidates, 1):
        title = paper.get("title", "Untitled")
        authors = ", ".join([a["name"] for a in paper.get("authors", [])[:3]])
        if len(paper.get("authors", [])) > 3:
            authors += " et al."
        source = paper.get("_source", "Unknown")
        nber_id = paper.get("nber_id", "")
        date = paper.get("publication_date", "")
        cited = paper.get("cited_by_count", 0)
        url = paper.get("url", "")
        relevance = paper.get("_relevance", 0)
        abstract = paper.get("abstract", "")

        lines.append(f"## {i}. {title}")
        if authors:
            lines.append(f"**Authors:** {authors}")
        meta_parts = [source]
        if nber_id:
            meta_parts.append(f"NBER: {nber_id}")
        if date:
            meta_parts.append(f"Date: {date}")
        if cited:
            meta_parts.append(f"Cited: {cited}")
        if relevance:
            meta_parts.append(f"Relevance: {relevance:.2f}")
        lines.append(f"**{' | '.join(meta_parts)}**")
        if url:
            lines.append(f"**URL:** {url}")
        # Add full abstract
        if abstract:
            lines.append(f"\n> {abstract}")
        # Add LLM insight for high-relevance papers
        paper_id = id(paper)
        if relevance > 0.8 and paper_id in high_paper_ids:
            insight_idx = high_paper_ids[paper_id]
            if insight_idx in llm_insights:
                lines.append(f"\n**LLM 分析：** {llm_insights[insight_idx]}")
        lines.append("")

    # Remove the end-of-document LLM section since we now put it per paper
    # (keeping the code for future reference but not using it)

    output = "\n".join(lines)

    # If format is delivery or telegram, also send via email
    if fmt in {"telegram", "delivery"}:
        # Get output root for saving files
        output_root = get_output_root(config)

        # Prepare candidates in the format expected by _deliver_report
        # Need to transform paper dicts to include proper author formatting
        candidates_for_delivery = []
        for p in top_candidates:
            paper_copy = dict(p)
            # Convert authors from [{"name": ...}] to ["name1", "name2"]
            authors_list = paper_copy.get("authors", [])
            if authors_list and isinstance(authors_list[0], dict):
                paper_copy["authors"] = [a.get("name", "") for a in authors_list if a.get("name")]
            candidates_for_delivery.append({"paper": paper_copy})

        # Format HTML for email - use candidates format
        from .html_fmt import format_digest_html
        html_content = format_digest_html(candidates_for_delivery, date_str)
        html_path = output_root / f"digest-all-{date_str}.html"
        html_path.write_text(html_content, encoding="utf-8")
        LOG.info("Wrote HTML digest to %s", html_path)

        # Format email body
        telegram_summary = format_digest_telegram(candidates_for_delivery, date_str)
        profile_summary = _load_profile_summary(profile_path, config)
        email_body_text, email_body_html = _format_digest_email_body(
            candidates_for_delivery,
            date_str=date_str,
            html_path=html_path,
            profile_summary=profile_summary,
        )

        # Save JSON
        digest_json_path = output_root / f"digest-all-{date_str}.json"
        digest_json_path.write_text(json.dumps({"candidates": candidates_for_delivery, "date": date_str}, indent=2), encoding="utf-8")

        # Send email
        email_cfg = _email_config(config)
        email_json_path = output_root / f"digest-all-{date_str}.email.json"
        email_status, final_email_json_path = _send_email_delivery(
            config=config,
            subject=_digest_email_subject(config, date_str=date_str, candidates=candidates_for_delivery),
            body_text=email_body_text,
            body_html=email_body_html,
            html_path=html_path,
            output_json_path=email_json_path,
        )
        LOG.info("Email: %s", email_status)

        if "ok" in email_status or "sent" in email_status:
            return f"Digest generated and sent to {email_cfg.get('recipients', [])}"
        else:
            return f"Digest generated but email failed: {email_status}"

    # Save to vault
    vault_path = Path.home() / "Documents" / "deadweight-notes" / "03_Resources" / "01_Raw_Literature" / "Digest"
    vault_path.mkdir(parents=True, exist_ok=True)
    output_file = vault_path / f"digest-{date_str}.md"
    output_file.write_text(output, encoding="utf-8")
    LOG.info("Saved digest to %s", output_file)

    return output


# Journal short name to OpenAlex ID mapping
JOURNAL_ALIAS = {
    # Economics
    "JPE": "S95323914",
    "QJE": "S203860005",
    "AER": "S23254222",
    "RES": "S88935262",
    "REStat": "S180061323",
    "EJ": "S45992627",
    "ECONOMETRICA": "S95464858",
    "JPubE": "S199447588",
    "JDE": "S101209419",
    "JUE": "S147692640",
    # Political Science
    "AJPS": "S90314269",
    "APSR": "S176007004",
    "BJPS": "S95691132",
    "PA": "S29331042",
    "WP": "S143110675",
    "GOVERNANCE": "S62375027",
    "RP": "S9731383",
}

JOURNAL_NAME = {v: k for k, v in JOURNAL_ALIAS.items()}

NBER_REPO_ID = "S2809516038"

# All sources for journal-digest
ALL_SOURCES = [NBER_REPO_ID] + list(JOURNAL_ALIAS.values())


def action_search(
    query: str,
    top: int = 20,
    source: str = "openalex",
    from_date: str | None = None,
) -> str:
    """Search papers on OpenAlex - unified search for NBER and journals.

    Args:
        query: Search keywords
        top: Number of results
        source: Source to search - "nber", "openalex" (all), journal short name (JPE, AER...), or "all"
        from_date: Filter by publication date
    """
    from .openalex_pipeline.client import search_journal_papers, search_and_parse, search_works

    keywords = [kw.strip() for kw in query.replace(",", " ").split() if kw.strip()]

    # Resolve source
    source_lower = source.lower() if source else "nber"

    if source_lower == "openalex":
        # Search all sources via OpenAlex (no journal restriction)
        LOG.info("Searching OpenAlex (all sources): keywords=%s", keywords)
        papers = search_works(keywords=keywords, from_date=from_date, per_page=top, sort="relevance_score:desc")
        source_label = "OpenAlex (All Sources)"
        # Format output with journal name
        lines = [f"# Search: \"{query}\"", f"**Source:** {source_label}\n", f"\nFound {len(papers)} papers:\n"]
        for i, p in enumerate(papers, 1):
            title = p.get("title", "Untitled")
            authors = ", ".join(a["name"] for a in p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            journal_name = p.get("_source", "Unknown")
            date = p.get("publication_date", "")
            cited = p.get("cited_by_count", 0)
            abstract = p.get("abstract", "")
            abstract_preview = abstract[:300] + "..." if len(abstract) > 300 else abstract
            url = p.get("url", "")

            lines.append(f"## {i}. {title}")
            if authors:
                lines.append(f"**Authors:** {authors}")
            meta_parts = [journal_name]
            if date:
                meta_parts.append(f"Date: {date}")
            if cited:
                meta_parts.append(f"Cited: {cited}")
            lines.append(f"**{' | '.join(meta_parts)}**")
            if url:
                lines.append(f"**URL:** {url}")
            if abstract_preview:
                lines.append(f"\n> {abstract_preview}")
            lines.append("")
        return "\n".join(lines)

    source_upper = source.upper() if source else "NBER"

    if source_upper == "NBER" or source_upper == "":
        # Search NBER only
        LOG.info("Searching NBER: keywords=%s", keywords)
        papers = search_and_parse(keywords=keywords, from_date=from_date, per_page=top)
        source_label = "NBER Working Papers"
        source_id = NBER_REPO_ID
    elif source_upper in JOURNAL_ALIAS:
        # Search specific journal
        source_id = JOURNAL_ALIAS[source_upper]
        source_label = f"{source_upper} ({source_id})"
        LOG.info("Searching %s: keywords=%s", source_label, keywords)
        papers = search_journal_papers(source_id=source_id, keywords=keywords, from_date=from_date, per_page=top)
    elif source_upper == "ALL":
        # Search all sources
        source_label = "All Sources (NBER + Journals)"
        LOG.info("Searching all sources: keywords=%s", keywords)
        papers = []
        # Search NBER
        nber_papers = search_and_parse(keywords=keywords, from_date=from_date, per_page=top)
        for p in nber_papers:
            p["_source"] = "NBER"
        papers.extend(nber_papers)
        # Search each journal
        for journal_name, journal_id in JOURNAL_ALIAS.items():
            try:
                journal_papers = search_journal_papers(source_id=journal_id, keywords=keywords, from_date=from_date, per_page=5)
                for p in journal_papers:
                    p["_source"] = journal_name
                papers.extend(journal_papers)
            except Exception as e:
                LOG.warning(f"Failed to search {journal_name}: {e}")
        # Sort by citations and limit
        papers.sort(key=lambda x: x.get("cited_by_count", 0), reverse=True)
        papers = papers[:top]
    else:
        # Unknown source, try as OpenAlex ID directly
        source_id = source
        source_label = f"Custom Source ({source_id})"
        LOG.info("Searching custom source %s: keywords=%s", source_id, keywords)
        papers = search_journal_papers(source_id=source_id, keywords=keywords, from_date=from_date, per_page=top)

    LOG.info("Found %d papers", len(papers))

    lines = [f"# Search: \"{query}\"", f"**Source:** {source_label}\n", f"\nFound {len(papers)} papers:\n"]
    for i, p in enumerate(papers, 1):
        title = p.get("title", "Untitled")
        authors = ", ".join(a["name"] for a in p.get("authors", [])[:3])
        if len(p.get("authors", [])) > 3:
            authors += " et al."
        nber_id = p.get("nber_id", "")
        source_tag = p.get("_source", "")
        date = p.get("publication_date", "")
        cited = p.get("cited_by_count", 0)
        abstract = p.get("abstract", "")
        abstract_preview = abstract[:300] + "..." if len(abstract) > 300 else abstract
        url = p.get("url", "")

        lines.append(f"## {i}. {title}")
        if authors:
            lines.append(f"**Authors:** {authors}")
        meta_parts = []
        if source_tag:
            meta_parts.append(source_tag)
        if nber_id:
            meta_parts.append(f"NBER: {nber_id}")
        if date:
            meta_parts.append(f"Date: {date}")
        if cited:
            meta_parts.append(f"Cited: {cited}")
        if meta_parts:
            lines.append(f"**{' | '.join(meta_parts)}**")
        if url:
            lines.append(f"**URL:** {url}")
        if abstract_preview:
            lines.append(f"\n{abstract_preview}")
        lines.append("")

    return "\n".join(lines)


def action_journal_search(query: str, journal: str, top: int = 20, from_date: str | None = None) -> str:
    """Search papers in a specific journal on OpenAlex. (Legacy, use action_search instead)"""
    return action_search(query=query, top=top, source=journal, from_date=from_date)


def action_nber_search(query: str, top: int = 20, from_date: str | None = None) -> str:
    """Search NBER working papers on OpenAlex. (Legacy, use action_search instead)"""
    return action_search(query=query, top=top, source="nber", from_date=from_date)


def main():
    parser = argparse.ArgumentParser(description="Codex Research Assist OpenClaw Runner")
    parser.add_argument("--action", required=True,
        choices=["search", "profile-refresh", "sync-index", "digest-all"],
        help="Action to perform")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config.json")
    parser.add_argument("--query", type=str, default="", help="Search query")
    parser.add_argument("--source", type=str, default="openalex",
        help="Source: openalex (all), nber, journal short name (JPE, AER...), or 'all' for all sources")
    parser.add_argument("--top", type=int, default=10, help="Number of results")
    parser.add_argument("--format", choices=["markdown", "telegram", "delivery"], default="markdown", help="Output format (default: markdown)")
    parser.add_argument("--force-rebuild", action="store_true", help="Force rebuild semantic index (for sync-index action)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(name)s %(levelname)s: %(message)s", stream=sys.stderr)

    try:
        if args.action == "search":
            if not args.query:
                parser.error("--query required for search action")
            output = action_search(args.query, top=args.top, source=args.source)

        # Legacy: nber-search -> search with nber source
        elif args.action == "nber-search":
            if not args.query:
                parser.error("--query required")
            output = action_search(args.query, top=args.top, source="nber")

        # Legacy: journal-search -> search with journal source
        elif args.action == "journal-search":
            if not args.query:
                parser.error("--query required")
            if not args.source or args.source == "nber":
                parser.error("--source required (e.g., --source JPE)")
            output = action_search(args.query, top=args.top, source=args.source)

        elif args.action == "digest-all":
            config = load_config(args.config)
            output = action_digest_all(config, fmt=args.format, config_path=args.config)

        elif args.action == "profile-refresh":
            config = load_config(args.config)
            output = action_profile_refresh(config)
        elif args.action == "sync-index":
            config = load_config(args.config)
            output = action_sync_index(config, config_path=args.config, force_rebuild=args.force_rebuild)
        else:
            parser.error(f"Unknown action: {args.action}")
        print(output)
    except Exception as exc:
        LOG.error("Error: %s", exc, exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
