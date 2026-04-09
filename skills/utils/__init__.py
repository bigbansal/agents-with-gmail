"""Shared utilities for the Gmail Skill."""
from .gmail_auth import get_gmail_service
from .email_parser import parse_message, list_messages
from .attachment_reader import read_attachment
from .summarizer import summarize_text, summarize_emails

__all__ = [
    "get_gmail_service",
    "parse_message",
    "list_messages",
    "read_attachment",
    "summarize_text",
    "summarize_emails",
]
