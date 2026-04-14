"""
auto_responder.py – Orchestrates sentiment-based auto-reply for emails.

Flow:
  1. Classify the email sentiment (POSITIVE / NEGATIVE / COMPLIANCE / NEUTRAL)
  2. If a template exists for that category, render it
  3. Send the auto-reply via the Gmail API
  4. Return a report of actions taken

Can operate on a single message or scan a batch (e.g. all unread).
"""
from __future__ import annotations

import logging
from typing import Any

from .email_parser import list_messages, parse_message
from .sentiment_analyzer import classify_email
from .email_templates import render_template

logger = logging.getLogger(__name__)

# Categories that should trigger an automatic reply
AUTO_REPLY_CATEGORIES = {"POSITIVE", "NEGATIVE", "COMPLIANCE"}


def analyse_and_respond(
    service,
    message_id: str,
    *,
    send_fn: Any = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Analyse a single email and auto-reply if the sentiment warrants it.

    Parameters
    ----------
    service : Gmail API service object (used to read the email)
    message_id : Gmail message ID
    send_fn : callable(to, subject, body) → dict – used to send the reply.
              Typically ``GmailSkill().send_email``.
    dry_run : if True, skip actual sending and just return what *would* happen.

    Returns
    -------
    dict with keys: message_id, classification, template_used, reply_sent, reply_result
    """
    msg = parse_message(service, message_id)

    classification = classify_email(
        subject=msg.get("subject", ""),
        body=msg.get("body", ""),
        sender=msg.get("sender", ""),
        date=msg.get("date", ""),
    )

    category = classification["category"]
    result: dict[str, Any] = {
        "message_id": message_id,
        "subject": msg.get("subject", ""),
        "sender": msg.get("sender", ""),
        "classification": classification,
        "template_used": False,
        "reply_sent": False,
        "reply_result": None,
    }

    if category not in AUTO_REPLY_CATEGORIES:
        result["note"] = "No auto-reply needed (NEUTRAL sentiment)."
        return result

    rendered = render_template(
        category,
        sender=msg.get("sender", ""),
        subject=msg.get("subject", ""),
        reason=classification.get("reason", ""),
    )
    if rendered is None:
        result["note"] = f"No template found for category {category}."
        return result

    result["template_used"] = True
    result["reply_subject"] = rendered["subject"]
    result["reply_body_preview"] = rendered["body"][:300]

    if dry_run:
        result["note"] = "Dry-run mode – reply NOT sent."
        return result

    if send_fn is None:
        result["note"] = "No send function provided – reply NOT sent."
        return result

    try:
        send_result = send_fn(
            to=msg["sender"],
            subject=rendered["subject"],
            body=rendered["body"],
        )
        result["reply_sent"] = True
        result["reply_result"] = send_result
    except Exception as exc:
        logger.exception("Failed to send auto-reply for %s", message_id)
        result["reply_sent"] = False
        result["reply_result"] = {"error": str(exc)}

    return result


def scan_and_respond(
    service,
    *,
    send_fn: Any = None,
    query: str = "is:unread in:inbox",
    max_results: int = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Scan a batch of emails, classify each, and auto-reply where appropriate.

    Returns a summary dict with per-email results.
    """
    stubs = list_messages(service, query=query, max_results=max_results)

    results: list[dict] = []
    stats = {"total": 0, "positive": 0, "negative": 0, "compliance": 0, "neutral": 0, "replies_sent": 0}

    for stub in stubs:
        try:
            r = analyse_and_respond(
                service,
                stub["id"],
                send_fn=send_fn,
                dry_run=dry_run,
            )
            results.append(r)
            cat = r["classification"]["category"].lower()
            stats["total"] += 1
            stats[cat] = stats.get(cat, 0) + 1
            if r.get("reply_sent"):
                stats["replies_sent"] += 1
        except Exception as exc:
            logger.exception("Error processing message %s", stub.get("id"))
            results.append({"message_id": stub.get("id"), "error": str(exc)})
            stats["total"] += 1

    return {"stats": stats, "results": results}
