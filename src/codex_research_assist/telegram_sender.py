"""Telegram sender module - bypasses LLM conversation flow.

This module sends messages DIRECTLY to Telegram Bot API via requests.
It NEVER goes through the LLM conversation flow to prevent context pollution.
"""

import os
from pathlib import Path

import requests


def send_message(
    text: str,
    *,
    chat_id: str | None = None,
    bot_token: str | None = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> dict:
    """Send a text message via Telegram Bot API. Returns API response dict."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    response = requests.post(url, json=payload, timeout=30)
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data.get('description', 'Unknown error')}")

    return data


def send_document(
    file_path: str | Path,
    *,
    caption: str | None = None,
    chat_id: str | None = None,
    bot_token: str | None = None,
    parse_mode: str = "HTML",
) -> dict:
    """Send a file as a Telegram Document attachment. Returns API response dict."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat}

        if caption:
            data["caption"] = caption
            data["parse_mode"] = parse_mode

        response = requests.post(url, data=data, files=files, timeout=60)

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result.get('description', 'Unknown error')}")

    return result


def send_digest(
    summary_text: str,
    html_path: str | Path,
    *,
    chat_id: str | None = None,
    bot_token: str | None = None,
) -> dict:
    """Send a digest: first the compact summary message, then the HTML file as attachment.
    Returns dict with both API responses.
    """
    message_response = send_message(
        summary_text,
        chat_id=chat_id,
        bot_token=bot_token,
    )

    document_response = send_document(
        html_path,
        caption="📎 Full digest (open in browser for best experience)",
        chat_id=chat_id,
        bot_token=bot_token,
    )

    return {
        "message": message_response,
        "document": document_response,
    }


def main():
    """CLI test interface."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Telegram sender")
    parser.add_argument("--text", help="Send a text message")
    parser.add_argument("--file", help="Send a file")
    parser.add_argument("--caption", help="Caption for file")

    args = parser.parse_args()

    if args.text:
        result = send_message(args.text)
        print(f"Message sent: {result['result']['message_id']}")
    elif args.file:
        result = send_document(args.file, caption=args.caption)
        print(f"Document sent: {result['result']['message_id']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
