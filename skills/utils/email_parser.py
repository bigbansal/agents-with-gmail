"""
Email parsing helpers.

Handles multi-part MIME messages, HTML → plain-text conversion
and attachment metadata extraction.
"""
from __future__ import annotations

import base64
import email
import os
import re
from datetime import datetime
from typing import Any

import html2text
from dateutil import parser as dateparser

_h2t = html2text.HTML2Text()
_h2t.ignore_links = False
_h2t.ignore_images = True


# ── Low-level message fetching ───────────────────────────────────────────────

def list_messages(
    service,
    query: str = "",
    max_results: int = 20,
    label_ids: list[str] | None = None,
) -> list[dict]:
    """
    Return a list of message stubs {id, threadId} matching *query*.

    Gmail search operators are supported, e.g. "is:unread after:2024/01/01".
    """
    kwargs: dict[str, Any] = {
        "userId": "me",
        "maxResults": max_results,
    }
    if query:
        kwargs["q"] = query
    if label_ids:
        kwargs["labelIds"] = label_ids

    result = service.users().messages().list(**kwargs).execute()
    return result.get("messages", [])


def get_raw_message(service, msg_id: str) -> dict:
    """Fetch a full message resource from the API."""
    return service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()


# ── Body & attachment extraction ─────────────────────────────────────────────

def _decode_b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "==")


def _extract_parts(payload: dict, body_parts: list, attachments: list) -> None:
    """Recursively walk MIME parts and collect body text + attachment metadata."""
    mime_type = payload.get("mimeType", "")
    parts = payload.get("parts")

    if parts:
        for part in parts:
            _extract_parts(part, body_parts, attachments)
        return

    body = payload.get("body", {})
    data = body.get("data")
    attachment_id = body.get("attachmentId")
    filename = payload.get("filename", "")

    if attachment_id or filename:
        attachments.append(
            {
                "filename": filename,
                "mimeType": mime_type,
                "attachmentId": attachment_id,
                "size": body.get("size", 0),
            }
        )
        return

    if data:
        text = _decode_b64(data).decode("utf-8", errors="replace")
        if mime_type == "text/html":
            text = _h2t.handle(text)
        body_parts.append(text.strip())


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ── Public: parse a single message ──────────────────────────────────────────

def parse_message(service, msg_id: str) -> dict:
    """
    Return a structured dict with keys:
        id, subject, sender, recipients, date, snippet, body, attachments
    """
    raw = get_raw_message(service, msg_id)
    payload = raw["payload"]
    headers = payload.get("headers", [])

    body_parts: list[str] = []
    attachments: list[dict] = []
    _extract_parts(payload, body_parts, attachments)

    date_str = _header(headers, "date")
    try:
        date = dateparser.parse(date_str)
    except Exception:
        date = None

    return {
        "id": raw["id"],
        "threadId": raw.get("threadId"),
        "subject": _header(headers, "subject") or "(no subject)",
        "sender": _header(headers, "from"),
        "recipients": _header(headers, "to"),
        "date": date.isoformat() if date else date_str,
        "snippet": raw.get("snippet", ""),
        "body": "\n\n".join(body_parts) or raw.get("snippet", ""),
        "labels": raw.get("labelIds", []),
        "attachments": attachments,
    }


def fetch_attachment_bytes(service, msg_id: str, attachment_id: str) -> bytes:
    """Download a specific attachment and return its raw bytes."""
    att = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=msg_id, id=attachment_id)
        .execute()
    )
    return _decode_b64(att["data"])
