"""
GmailSkill – Codex-compatible skill for Gmail.

Exposed skill actions (callable by the Codex agent loop):
  • send_email          – compose and send an email
  • read_email          – read a specific email by ID
  • search_emails       – search the inbox with a Gmail query
  • list_unread         – list unread messages
  • summarize_email     – AI summary of one email (+ attachments)
  • day_summary         – AI briefing of today's inbox
  • read_attachment     – extract and optionally summarise an attachment
  • mark_read           – mark one or more messages as read
  • reply_email         – reply to an existing thread
  • delete_email        – move a message to trash
"""
from __future__ import annotations

import base64
import os
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from dotenv import load_dotenv

from .utils.gmail_auth import get_gmail_service
from .utils.email_parser import list_messages, parse_message, fetch_attachment_bytes
from .utils.attachment_reader import read_attachment as _read_attachment_bytes
from .utils.summarizer import (
    summarize_email as _ai_summarize_email,
    summarize_emails as _ai_summarize_emails,
    summarize_text as _ai_summarize_text,
)

load_dotenv()

MAX_EMAILS_FOR_DAY_SUMMARY = int(os.getenv("MAX_EMAILS_FOR_DAY_SUMMARY", "20"))


class GmailSkill:
    """
    Codex skill: full Gmail access.

    Usage (standalone):
        skill = GmailSkill()
        skill.send_email(to="alice@example.com", subject="Hi", body="Hello!")
        summary = skill.day_summary()
    """

    SKILL_NAME = "gmail"
    SKILL_DESCRIPTION = (
        "Send, read, search and summarise Gmail messages. "
        "Can also parse PDF and Excel attachments."
    )

    # Schema understood by Codex tool-calling loop
    ACTIONS: list[dict] = [
        {
            "name": "send_email",
            "description": "Send an email from the authenticated Gmail account.",
            "parameters": {
                "to": "Recipient email address (required)",
                "subject": "Email subject (required)",
                "body": "Plain-text email body (required)",
                "cc": "Comma-separated CC addresses (optional)",
                "bcc": "Comma-separated BCC addresses (optional)",
            },
        },
        {
            "name": "read_email",
            "description": "Read a specific email by its Gmail message ID.",
            "parameters": {
                "message_id": "Gmail message ID (required)",
            },
        },
        {
            "name": "search_emails",
            "description": "Search emails using Gmail query syntax (e.g. 'is:unread from:boss@co.com').",
            "parameters": {
                "query": "Gmail search query (required)",
                "max_results": "Max emails to return (default 10)",
            },
        },
        {
            "name": "list_unread",
            "description": "List unread messages in the inbox.",
            "parameters": {
                "max_results": "Max emails to return (default 10)",
            },
        },
        {
            "name": "summarize_email",
            "description": "AI-powered summary of one email including its attachments.",
            "parameters": {
                "message_id": "Gmail message ID (required)",
                "include_attachments": "Whether to read & summarise attachments (default true)",
            },
        },
        {
            "name": "day_summary",
            "description": "AI briefing of today's emails, categorised by priority.",
            "parameters": {
                "date_str": "Date in YYYY-MM-DD format (default: today)",
            },
        },
        {
            "name": "read_attachment",
            "description": "Extract text from a specific attachment (PDF / Excel / CSV / txt).",
            "parameters": {
                "message_id": "Gmail message ID (required)",
                "filename": "Filename of the attachment (required)",
                "summarize": "Return AI summary instead of raw text (default false)",
            },
        },
        {
            "name": "reply_email",
            "description": "Reply to an existing email thread.",
            "parameters": {
                "message_id": "ID of the message to reply to (required)",
                "body": "Reply body (required)",
            },
        },
        {
            "name": "mark_read",
            "description": "Mark one or more messages as read.",
            "parameters": {
                "message_ids": "List of Gmail message IDs (required)",
            },
        },
        {
            "name": "delete_email",
            "description": "Move a message to the Trash.",
            "parameters": {
                "message_id": "Gmail message ID (required)",
            },
        },
    ]

    # ── Initialisation ────────────────────────────────────────────────────────

    def __init__(self):
        self._service = None  # lazy initialisation

    @property
    def service(self):
        if self._service is None:
            self._service = get_gmail_service()
        return self._service

    # ── Codex dispatcher ──────────────────────────────────────────────────────

    def run(self, action: str, **kwargs) -> Any:
        """
        Generic dispatcher used by Codex agent loop.

        skill.run("send_email", to="a@b.com", subject="Hi", body="Hey")
        """
        handler = getattr(self, action, None)
        if handler is None:
            raise ValueError(
                f"Unknown Gmail skill action: '{action}'. "
                f"Available: {[a['name'] for a in self.ACTIONS]}"
            )
        return handler(**kwargs)

    # ── Actions ───────────────────────────────────────────────────────────────

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict:
        """Compose and send an email."""
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return {"status": "sent", "message_id": sent["id"]}

    def read_email(self, message_id: str) -> dict:
        """Return a structured dict for one email."""
        return parse_message(self.service, message_id)

    def search_emails(self, query: str, max_results: int = 10) -> list[dict]:
        """Search emails and return a list of parsed messages."""
        stubs = list_messages(self.service, query=query, max_results=int(max_results))
        results = []
        for stub in stubs:
            try:
                results.append(parse_message(self.service, stub["id"]))
            except Exception as exc:
                results.append({"id": stub["id"], "error": str(exc)})
        return results

    def list_unread(self, max_results: int = 10) -> list[dict]:
        """Return unread inbox messages."""
        return self.search_emails(
            query="is:unread in:inbox", max_results=int(max_results)
        )

    def summarize_email(
        self,
        message_id: str,
        include_attachments: bool = True,
    ) -> dict:
        """
        AI summary of a single email.
        If include_attachments=True, also reads and summarises each attachment.
        """
        msg = parse_message(self.service, message_id)
        email_summary = _ai_summarize_email(msg)

        attachment_summaries: list[dict] = []
        if include_attachments and msg.get("attachments"):
            for att in msg["attachments"]:
                att_id = att.get("attachmentId")
                if not att_id:
                    continue
                try:
                    raw_bytes = fetch_attachment_bytes(
                        self.service, message_id, att_id
                    )
                    parsed = _read_attachment_bytes(
                        raw_bytes, att["filename"], att.get("mimeType", "")
                    )
                    att_summary = _ai_summarize_text(
                        parsed["content"],
                        context=f"attachment '{att['filename']}' in email '{msg['subject']}'",
                    )
                    attachment_summaries.append(
                        {
                            "filename": att["filename"],
                            "mime_type": att.get("mimeType", ""),
                            "summary": att_summary,
                        }
                    )
                except Exception as exc:
                    attachment_summaries.append(
                        {"filename": att["filename"], "error": str(exc)}
                    )

        return {
            "message_id": message_id,
            "subject": msg["subject"],
            "sender": msg["sender"],
            "date": msg["date"],
            "summary": email_summary,
            "attachments": attachment_summaries,
        }

    def day_summary(self, date_str: str = "") -> dict:
        """
        Fetch emails from *date_str* (default today) and return an AI briefing.
        """
        if not date_str:
            date_str = date.today().isoformat()

        # Gmail date query:  after:YYYY/MM/DD before:YYYY/MM/DD
        d = datetime.strptime(date_str, "%Y-%m-%d")
        after = d.strftime("%Y/%m/%d")
        # Include the whole day (before next day)
        from datetime import timedelta
        next_day = (d + timedelta(days=1)).strftime("%Y/%m/%d")

        query = f"after:{after} before:{next_day}"
        stubs = list_messages(
            self.service, query=query, max_results=MAX_EMAILS_FOR_DAY_SUMMARY
        )

        messages: list[dict] = []
        for stub in stubs:
            try:
                messages.append(parse_message(self.service, stub["id"]))
            except Exception:
                pass

        summary_text = _ai_summarize_emails(messages, period=date_str)
        return {
            "date": date_str,
            "email_count": len(messages),
            "summary": summary_text,
        }

    def read_attachment(
        self,
        message_id: str,
        filename: str,
        summarize: bool = False,
    ) -> dict:
        """
        Find *filename* in a message's attachments, extract its text
        and optionally return an AI summary.
        """
        msg = parse_message(self.service, message_id)
        target = None
        for att in msg.get("attachments", []):
            if att["filename"].lower() == filename.lower():
                target = att
                break

        if target is None:
            available = [a["filename"] for a in msg.get("attachments", [])]
            raise FileNotFoundError(
                f"Attachment '{filename}' not found in message {message_id}. "
                f"Available: {available}"
            )

        raw_bytes = fetch_attachment_bytes(
            self.service, message_id, target["attachmentId"]
        )
        parsed = _read_attachment_bytes(
            raw_bytes, target["filename"], target.get("mimeType", "")
        )

        result = {
            "message_id": message_id,
            "filename": target["filename"],
            "mime_type": target.get("mimeType", ""),
            "content": parsed["content"],
        }

        if summarize:
            result["summary"] = _ai_summarize_text(
                parsed["content"],
                context=f"attachment '{target['filename']}'",
            )

        return result

    def reply_email(self, message_id: str, body: str) -> dict:
        """Reply to an email thread."""
        original = parse_message(self.service, message_id)
        reply = MIMEText(body, "plain")
        reply["To"] = original["sender"]
        reply["Subject"] = (
            original["subject"]
            if original["subject"].lower().startswith("re:")
            else f"Re: {original['subject']}"
        )
        reply["In-Reply-To"] = message_id
        reply["References"] = message_id

        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        sent = (
            self.service.users()
            .messages()
            .send(
                userId="me",
                body={"raw": raw, "threadId": original.get("threadId")},
            )
            .execute()
        )
        return {"status": "replied", "message_id": sent["id"]}

    def mark_read(self, message_ids: list[str]) -> dict:
        """Remove the UNREAD label from one or more messages."""
        if isinstance(message_ids, str):
            message_ids = [message_ids]
        self.service.users().messages().batchModify(
            userId="me",
            body={
                "ids": message_ids,
                "removeLabelIds": ["UNREAD"],
            },
        ).execute()
        return {"status": "marked_read", "count": len(message_ids)}

    def delete_email(self, message_id: str) -> dict:
        """Move a message to Trash."""
        self.service.users().messages().trash(
            userId="me", id=message_id
        ).execute()
        return {"status": "trashed", "message_id": message_id}
