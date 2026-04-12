"""
guardrails.py – Sensitive-data redaction layer.

Scrubs text and OpenAI-format message lists before they are sent to
the OpenAI / Codex API, ensuring that PII and secrets are never
transmitted to an external model.

Detected & redacted categories
───────────────────────────────
  • Credit card numbers  (Visa, MC, Amex, Discover, Diners, JCB)
  • US Social Security Numbers  (xxx-xx-xxxx)
  • Passwords / secrets in key=value form
  • API keys, bearer tokens, access tokens
  • AWS access key IDs
  • PEM private key blocks
  • Bank/routing numbers with contextual keywords
  • IBAN numbers
  • US & international phone numbers
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
from typing import Any

# Load .env BEFORE reading env vars so OPENAI_LOG_FILE is available at import time
# Use the skill's own directory (not CWD, which varies depending on who runs it)
try:
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load_dotenv
    # guardrails.py lives at <skill_root>/skills/utils/guardrails.py
    # → go up two levels to reach <skill_root>
    _SKILL_ROOT = _Path(__file__).resolve().parent.parent.parent
    _load_dotenv(dotenv_path=_SKILL_ROOT / ".env")
except ImportError:
    _SKILL_ROOT = None

logger = logging.getLogger(__name__)

# ── Payload logger ─────────────────────────────────────────────────────────────
# Set OPENAI_LOG_FILE=openai_payloads.log in .env to capture every outgoing
# OpenAI request to a local file for inspection.
_LOG_FILE_RAW: str = os.getenv("OPENAI_LOG_FILE", "")
# Resolve relative paths against the skill root so the file is always
# created in a predictable place regardless of Codex's CWD.
if _LOG_FILE_RAW and not os.path.isabs(_LOG_FILE_RAW) and _SKILL_ROOT:
    _LOG_FILE: str = str(_SKILL_ROOT / _LOG_FILE_RAW)
else:
    _LOG_FILE = _LOG_FILE_RAW


def _log_payload(label: str, payload: str) -> None:
    """Append a timestamped payload snapshot to OPENAI_LOG_FILE."""
    if not _LOG_FILE:
        return
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    separator = "=" * 72
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{separator}\n[{ts}] {label}\n{separator}\n")
        f.write(payload)
        f.write("\n")

# ── Pattern registry ───────────────────────────────────────────────────────────
# Each entry: (name, compiled_pattern, replacement_label)

_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # ── Secrets / credentials ──────────────────────────────────────────────
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----.*?"
            r"-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|AGPA|AROA|AIPA|ANPA|ANVA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        "api_key_or_token",
        re.compile(
            r"(?i)(?:api[_\-]?key|access[_\-]?token|auth[_\-]?token|"
            r"secret[_\-]?key|bearer|client[_\-]?secret)\s*[:=]\s*\S+",
        ),
        "[REDACTED_API_KEY]",
    ),
    (
        "password",
        re.compile(
            r"(?i)(?:password|passwd|pwd|passphrase)\s*[:=]\s*\S+",
        ),
        "[REDACTED_PASSWORD]",
    ),
    # ── Financial ──────────────────────────────────────────────────────────
    (
        "credit_card",
        re.compile(
            r"\b(?:"
            r"4[0-9]{12}(?:[0-9]{3})?"          # Visa (13 or 16 digits)
            r"|5[1-5][0-9]{14}"                  # Mastercard
            r"|2(?:2[2-9][1-9]|[3-6]\d{2}|7[01]\d|720)\d{12}"  # Mastercard 2xxx
            r"|3[47][0-9]{13}"                   # American Express
            r"|3(?:0[0-5]|[68][0-9])[0-9]{11}"  # Diners Club
            r"|6(?:011|5[0-9]{2})[0-9]{12}"      # Discover
            r"|(?:2131|1800|35\d{3})\d{11}"      # JCB
            r")\b",
        ),
        "[REDACTED_CREDIT_CARD]",
    ),
    (
        "iban",
        re.compile(
            r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]{0,16})?\b",
        ),
        "[REDACTED_IBAN]",
    ),
    (
        "bank_account_with_context",
        re.compile(
            r"(?i)(?:account\s*(?:number|no|#)|routing\s*(?:number|no|#)|"
            r"acct\s*(?:no|#)?)\s*[:.]?\s*(\d[\d\s\-]{6,19}\d)",
        ),
        "[REDACTED_BANK_ACCOUNT]",
    ),
    # ── Identity ───────────────────────────────────────────────────────────
    (
        "ssn",
        re.compile(
            r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
        ),
        "[REDACTED_SSN]",
    ),
    (
        "phone_number",
        re.compile(
            r"(?<!\d)"                               # no leading digit
            r"(?:\+?1[\s.\-]?)?"                     # optional country code
            r"(?:\(\d{3}\)|\d{3})[\s.\-]?"           # area code
            r"\d{3}[\s.\-]?\d{4}"
            r"(?!\d)",                               # no trailing digit
        ),
        "[REDACTED_PHONE]",
    ),
]


# ── Core scrubbing function ────────────────────────────────────────────────────

def scrub(text: str) -> tuple[str, list[str]]:
    """
    Redact all sensitive patterns from *text*.

    Returns
    -------
    scrubbed : str
        The text with sensitive data replaced by placeholder tokens.
    findings : list[str]
        Human-readable list of what was redacted (for logging).
    """
    if not isinstance(text, str) or not text:
        return text, []

    findings: list[str] = []
    scrubbed = text

    for name, pattern, replacement in _PATTERNS:
        scrubbed, n = pattern.subn(replacement, scrubbed)
        if n:
            findings.append(f"{name} ×{n}")

    if findings:
        logger.warning(
            "Guardrails: redacted before sending to OpenAI → %s",
            ", ".join(findings),
        )

    return scrubbed, findings


def scrub_text(text: str) -> str:
    """Convenience wrapper – returns only the scrubbed text."""
    result, _ = scrub(text)
    return result


# ── OpenAI message-list scrubber ──────────────────────────────────────────────

def scrub_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Return a deep-scrubbed copy of an OpenAI-format conversation list.

    Handles:
      • Simple string *content* fields
      • Lists of content parts (multimodal format)
      • Tool result messages
    Skips the system message so instructions are never altered.
    """
    cleaned: list[dict[str, Any]] = []

    for msg in messages:
        msg = dict(msg)  # shallow copy; we'll replace content
        role = msg.get("role", "")

        if role == "system":
            # Never modify the system prompt
            cleaned.append(msg)
            continue

        content = msg.get("content")

        if isinstance(content, str):
            msg["content"] = scrub_text(content)

        elif isinstance(content, list):
            # Multimodal / structured content
            new_parts = []
            for part in content:
                part = dict(part)
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    part["text"] = scrub_text(part["text"])
                new_parts.append(part)
            msg["content"] = new_parts

        cleaned.append(msg)

    # Log the exact payload that will be sent to OpenAI
    _log_payload(
        "scrub_messages() → OpenAI conversation payload",
        json.dumps(cleaned, ensure_ascii=False, indent=2, default=str),
    )
    return cleaned


# ── Quick self-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _samples = [
        "My card is 4111111111111111 and SSN 123-45-6789.",
        "password=SuperSecret123!",
        "API_KEY=sk-1234567890abcdef",
        "Call me at (415) 555-1234 or +1 800 555-0199.",
        "IBAN: GB82WEST12345698765432",
        "Account number: 123456789",
        "Routing number: 021000021",
    ]
    for s in _samples:
        result, found = scrub(s)
        print(f"IN : {s}")
        print(f"OUT: {result}")
        print(f"    [{', '.join(found) if found else 'nothing detected'}]")
        print()
