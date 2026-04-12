"""
AI summarisation utilities backed by the OpenAI Chat Completions API.
"""
from __future__ import annotations

import os
import textwrap
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .guardrails import scrub_text

load_dotenv()

_client: OpenAI | None = None
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Token budget: leave room for system prompt + response
_MAX_BODY_CHARS = 12_000


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it to your .env file."
            )
        _client = OpenAI(api_key=key)
    return _client


def _truncate(text: str, max_chars: int = _MAX_BODY_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[… content truncated to {max_chars:,} chars]"


def _chat(system: str, user: str) -> str:
    """Send a single-turn chat request and return the assistant message."""
    import json as _json
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # Log the exact payload being sent (text is already scrubbed before _chat is called)
    from .guardrails import _log_payload
    _log_payload(
        f"summarizer._chat() → OpenAI [model={MODEL}]",
        _json.dumps(messages, ensure_ascii=False, indent=2),
    )
    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# ── Public helpers ────────────────────────────────────────────────────────────

def summarize_text(text: str, context: str = "an email attachment") -> str:
    """Return a concise summary of arbitrary text (e.g. PDF / Excel content)."""
    system = (
        "You are a helpful assistant that produces clear, concise summaries. "
        "Focus on key facts, numbers, action items and decisions. "
        "Use bullet points where helpful."
    )
    user = (
        f"Please summarise the following content from {context}:\n\n"
        + _truncate(scrub_text(text))
    )
    return _chat(system, user)


def summarize_email(msg: dict[str, Any]) -> str:
    """Return a one-paragraph summary of a single email."""
    body = scrub_text(msg.get("body") or msg.get("snippet", ""))
    system = (
        "You are a helpful email assistant. Summarise the email in 2-4 sentences, "
        "highlighting the sender's main ask or point and any deadlines or actions required."
    )
    user = textwrap.dedent(f"""\
        Subject : {scrub_text(msg.get('subject', '(none)'))}
        From    : {scrub_text(msg.get('sender', ''))}
        Date    : {msg.get('date', '')}

        Body:
        {_truncate(body, 6000)}
    """)
    return _chat(system, user)


def summarize_emails(messages: list[dict[str, Any]], period: str = "today") -> str:
    """
    Given a list of parsed email dicts, produce a consolidated "day summary"
    with categories: Action Required, FYI, Newsletters/Promos, Other.
    """
    if not messages:
        return f"No emails found for {period}."

    # Build a compact digest to stay within context window
    digest_lines: list[str] = []
    for i, m in enumerate(messages, 1):
        snippet = scrub_text(
            (m.get("body") or m.get("snippet", ""))[:400].replace("\n", " ")
        )
        digest_lines.append(
            f"{i}. [{m.get('date', '')}] From: {scrub_text(m.get('sender', ''))} | "
            f"Subject: {scrub_text(m.get('subject', ''))} | Preview: {snippet}"
        )
    digest = "\n".join(digest_lines)

    system = (
        "You are an executive assistant. Given a digest of emails, produce a structured "
        "daily briefing with these sections:\n"
        "1. **Action Required** – emails needing a reply or task\n"
        "2. **Important Updates** – news, decisions, information to be aware of\n"
        "3. **FYI / Low Priority** – informational emails\n"
        "4. **Promotions / Newsletters** – marketing or automated emails\n\n"
        "For each email cite its number (e.g. #3). Be concise."
    )
    user = f"Here are the emails for {period}:\n\n{_truncate(digest, _MAX_BODY_CHARS)}"
    return _chat(system, user)
