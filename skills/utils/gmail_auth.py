"""
Gmail OAuth2 authentication helper.

Flow:
1. First run  → opens browser for consent, saves token.json
2. Subsequent → loads token.json and refreshes silently if needed
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = os.getenv(
    "GMAIL_SCOPES",
    "https://www.googleapis.com/auth/gmail.modify",
).split()

CREDENTIALS_PATH = Path(os.getenv("GMAIL_CREDENTIALS_PATH", "config/credentials.json"))
TOKEN_PATH = Path(os.getenv("GMAIL_TOKEN_PATH", "config/token.json"))


def get_gmail_service():
    """Return an authorised Gmail API service object."""
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing Gmail credentials file: {CREDENTIALS_PATH}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)
