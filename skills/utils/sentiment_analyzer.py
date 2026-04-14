"""
sentiment_analyzer.py – AI-powered email sentiment & intent classifier.

Uses OpenAI to classify an email into one of the following categories:
  • POSITIVE        – appreciation, praise, satisfaction
  • NEGATIVE        – complaint, frustration, dissatisfaction
  • COMPLIANCE      – legal, regulatory, policy or compliance concern
  • NEUTRAL         – informational, no strong sentiment

Returns a structured dict with the category, confidence, and a short reason.
"""
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .guardrails import scrub_text

load_dotenv()

_client: OpenAI | None = None
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

_CLASSIFICATION_SYSTEM = """\
You are an email sentiment and intent classifier. Analyse the email below and
return a JSON object with EXACTLY these keys:

{
  "category": "<POSITIVE | NEGATIVE | COMPLIANCE | NEUTRAL>",
  "confidence": <float 0-1>,
  "reason": "<one-sentence justification>"
}

Classification rules:
- POSITIVE: the sender expresses appreciation, praise, satisfaction, or good news.
- NEGATIVE: the sender expresses complaint, frustration, dissatisfaction, anger,
  a service issue, or escalation intent.
- COMPLIANCE: the email raises legal, regulatory, data-privacy, audit, policy-violation,
  or compliance-related concerns (e.g. GDPR, HIPAA, SOX, internal policy breaches).
- NEUTRAL: purely informational, no strong sentiment or compliance concern.

Return ONLY the JSON object, no markdown fences or extra text.
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        _client = OpenAI(api_key=key)
    return _client


def classify_email(
    subject: str,
    body: str,
    sender: str = "",
    *,
    date: str = "",
) -> dict[str, Any]:
    """
    Classify a single email and return::

        {
            "category": "NEGATIVE",
            "confidence": 0.92,
            "reason": "The sender complains about delayed delivery."
        }
    """
    user_prompt = (
        f"Subject: {scrub_text(subject)}\n"
        f"From: {scrub_text(sender)}\n"
        f"Date: {date}\n\n"
        f"Body:\n{scrub_text(body[:6000])}"
    )

    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _CLASSIFICATION_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()

    # Robustly parse the JSON (strip markdown fences if present)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "category": "NEUTRAL",
            "confidence": 0.0,
            "reason": f"Failed to parse classifier output: {raw[:200]}",
        }

    # Normalise
    result["category"] = result.get("category", "NEUTRAL").upper()
    if result["category"] not in {"POSITIVE", "NEGATIVE", "COMPLIANCE", "NEUTRAL"}:
        result["category"] = "NEUTRAL"

    return result
