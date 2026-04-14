"""
email_templates.py – Built-in response templates for auto-triggered emails.

Each template is a dict with:
  • subject_prefix  – prepended to the original subject
  • body            – the template body (supports {sender}, {subject},
                      {reason} placeholders)

Templates can be customised via AUTO_REPLY_TEMPLATES env-var pointing to a
JSON file, or by editing the defaults below.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ── Default built-in templates ────────────────────────────────────────────────

_BUILTIN_TEMPLATES: dict[str, dict[str, str]] = {
    "NEGATIVE": {
        "subject_prefix": "Re: [We're on it] ",
        "body": (
            "Dear {sender_name},\n\n"
            "Thank you for reaching out. We sincerely apologise for the inconvenience "
            "you've experienced regarding \"{subject}\".\n\n"
            "Your concern has been flagged as high-priority and a member of our team "
            "will follow up with you within 24 hours with a resolution.\n\n"
            "We value your feedback and are committed to making this right.\n\n"
            "Best regards,\n"
            "Customer Support Team"
        ),
    },
    "POSITIVE": {
        "subject_prefix": "Re: [Thank you!] ",
        "body": (
            "Dear {sender_name},\n\n"
            "Thank you so much for your kind words regarding \"{subject}\"! "
            "We truly appreciate your positive feedback.\n\n"
            "It's great to know that our efforts are making a difference. "
            "We'll share your message with the team – it means a lot to us.\n\n"
            "If there's anything else we can help with, please don't hesitate "
            "to reach out.\n\n"
            "Warm regards,\n"
            "Customer Success Team"
        ),
    },
    "COMPLIANCE": {
        "subject_prefix": "Re: [Compliance Review Initiated] ",
        "body": (
            "Dear {sender_name},\n\n"
            "We have received your email regarding \"{subject}\" and recognise that "
            "it raises a compliance-related concern.\n\n"
            "This matter has been escalated to our Compliance & Legal team for "
            "immediate review. You can expect a formal acknowledgement within "
            "48 business hours.\n\n"
            "In the meantime, please refrain from sharing additional sensitive "
            "information over email. A secure channel will be provided if needed.\n\n"
            "Thank you for bringing this to our attention.\n\n"
            "Regards,\n"
            "Compliance Office"
        ),
    },
}


def _load_custom_templates() -> dict[str, dict[str, str]] | None:
    """Load user-overridden templates from a JSON file if configured."""
    path = os.getenv("AUTO_REPLY_TEMPLATES")
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def get_templates() -> dict[str, dict[str, str]]:
    """Return active templates (custom overrides merged onto defaults)."""
    templates = dict(_BUILTIN_TEMPLATES)
    custom = _load_custom_templates()
    if custom:
        templates.update(custom)
    return templates


def render_template(
    category: str,
    *,
    sender: str = "",
    subject: str = "",
    reason: str = "",
) -> dict[str, str] | None:
    """
    Render the template for *category*.

    Returns ``{"subject": "...", "body": "..."}`` or ``None`` if the
    category has no template (e.g. NEUTRAL).
    """
    templates = get_templates()
    tpl = templates.get(category.upper())
    if tpl is None:
        return None

    # Derive a friendly sender name (first part of email or the whole string)
    sender_name = sender.split("@")[0].replace(".", " ").title() if sender else "there"

    rendered_subject = tpl["subject_prefix"] + subject
    rendered_body = tpl["body"].format(
        sender=sender,
        sender_name=sender_name,
        subject=subject,
        reason=reason,
    )
    return {"subject": rendered_subject, "body": rendered_body}
