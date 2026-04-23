"""Email sender for paper-finder delivery."""

from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _build_message(
    *,
    subject: str,
    body_text: str,
    body_html: str | None,
    sender: str,
    recipients: list[str],
    attachments: list[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    for attachment_path in attachments:
        mime_type, _ = mimetypes.guess_type(attachment_path.name)
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        payload = attachment_path.read_bytes()
        message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=attachment_path.name)

    return message


def send_email(
    *,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    sender: str,
    recipients: list[str],
    smtp_server: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    tls_mode: str = "ssl",
    timeout: int = 20,
    attachments: list[str | Path] | None = None,
) -> dict[str, Any]:
    recipient_list = _as_string_list(recipients)
    if not sender.strip():
        raise RuntimeError("Email sender is not configured")
    if not recipient_list:
        raise RuntimeError("Email recipients are not configured")
    if not smtp_server.strip():
        raise RuntimeError("SMTP server is not configured")
    if not smtp_user.strip() or not smtp_pass.strip():
        raise RuntimeError("SMTP credentials are not configured")

    attachment_paths = [Path(item).expanduser().resolve() for item in (attachments or [])]
    message = _build_message(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        sender=sender,
        recipients=recipient_list,
        attachments=attachment_paths,
    )

    mode = tls_mode.strip().lower()
    if mode == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout, context=context) as smtp:
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(message)
    elif mode == "starttls":
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(message)
    elif mode == "plain":
        with smtplib.SMTP(smtp_server, smtp_port, timeout=timeout) as smtp:
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(message)
    else:
        raise RuntimeError(f"Unsupported email tls_mode: {tls_mode}")

    return {
        "ok": True,
        "recipients": recipient_list,
        "sender": sender,
        "subject": subject,
        "attachments": [path.as_posix() for path in attachment_paths],
    }
