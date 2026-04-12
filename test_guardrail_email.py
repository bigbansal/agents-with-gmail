"""
test_guardrail_email.py
───────────────────────
End-to-end guardrail smoke test:

  1. Authenticates with Gmail (reuses existing token.json)
  2. Auto-detects your Gmail address
  3. Sends a test email to yourself that contains deliberately
     embedded sensitive data (fake, but realistic-looking)
  4. Waits a moment, then reads the email back via GmailSkill
  5. Shows the raw email body vs what the guardrail actually
     sends to OpenAI — every piece of sensitive data should
     be replaced with a [REDACTED_…] token.

Run:
    python test_guardrail_email.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time

# ── Bootstrap path ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

# ── Load guardrails without full package import ────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "guardrails",
    os.path.join(os.path.dirname(__file__), "skills", "utils", "guardrails.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
scrub_text = _mod.scrub_text

# ── GmailSkill & auth ──────────────────────────────────────────────────────────
from skills.utils.gmail_auth import get_gmail_service
from skills.gmail_skill import GmailSkill
from skills.utils.email_parser import list_messages, parse_message

# ── ANSI colours ───────────────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

DIVIDER = "─" * 64

# ── Fake-but-realistic sensitive payload ──────────────────────────────────────
SENSITIVE_BODY = """\
Hi,

This is a guardrail smoke-test email. It intentionally contains
fake sensitive data to verify that the redaction layer works before
anything is forwarded to OpenAI.

--- Fake Credentials ---
  API key      : api_key=sk-FAKEFAKEFAKEFAKEFAKEFAKEFAKE1234567890abcdef
  AWS key      : AKIAIOSFODNN7EXAMPLE
  Password     : password=Sup3rS3cr3t!

--- Fake Financial Data ---
  Credit card  : 4111 1111 1111 1111  (Visa test number)
  Amex         : 3782 822463 10005
  SSN          : 123-45-6789
  IBAN         : GB82WEST12345698765432
  Account No.  : Account number: 9876543210
  Routing No.  : Routing number: 021000021

--- Fake Contact Info ---
  Phone (US)   : (415) 555-0123
  Phone (Intl) : +1 800-555-0199

--- Legitimate Content (must NOT be redacted) ---
  Meeting tomorrow at 3 pm.
  Budget estimate: $1,234.56
  Contact: alice@example.com

Thanks,
Guardrail Test Bot
"""

SUBJECT = "[GUARDRAIL TEST] Sensitive data redaction smoke test"


def _banner(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{DIVIDER}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{DIVIDER}{RESET}")


def main() -> None:
    _banner("Connecting to Gmail …")
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    my_email = profile["emailAddress"]
    print(f"  Authenticated as: {BOLD}{my_email}{RESET}")

    skill = GmailSkill()

    # ── 1. Send the test email to ourselves ────────────────────────────────────
    _banner("Sending test email to yourself …")
    send_result = skill.run(
        "send_email",
        to=my_email,
        subject=SUBJECT,
        body=SENSITIVE_BODY,
    )
    print(f"  {GREEN}Sent!{RESET}  status={send_result.get('status')}  id={send_result.get('id')}")

    # ── 2. Give Gmail a moment to ingest the message ───────────────────────────
    print("\n  Waiting 5 s for Gmail to ingest the message …", end="", flush=True)
    time.sleep(5)
    print(" done.")

    # ── 3. Find the message we just sent ──────────────────────────────────────
    _banner("Fetching email from inbox …")
    stubs = list_messages(
        service,
        query=f'subject:"{SUBJECT}" in:anywhere',
        max_results=1,
    )
    if not stubs:
        print(f"  {RED}Could not find the test email. Try running again in a few seconds.{RESET}")
        sys.exit(1)

    msg_id = stubs[0]["id"]
    msg = parse_message(service, msg_id)
    raw_body = msg.get("body") or msg.get("snippet", "")
    print(f"  Found message id: {msg_id}")

    # ── 4. Show raw body ────────────────────────────────────────────────────────
    _banner("RAW email body (what Gmail returned)")
    print(raw_body)

    # ── 5. Run guardrail ────────────────────────────────────────────────────────
    _banner("SCRUBBED body (what OpenAI would receive)")
    scrubbed = scrub_text(raw_body)
    print(scrubbed)

    # ── 6. Side-by-side diff of what was changed ───────────────────────────────
    _banner("What was redacted?")
    raw_lines    = raw_body.splitlines()
    scrub_lines  = scrubbed.splitlines()
    changes = 0
    for r, s in zip(raw_lines, scrub_lines):
        if r != s:
            print(f"  {RED}- {r.strip()}{RESET}")
            print(f"  {GREEN}+ {s.strip()}{RESET}")
            changes += 1

    if changes == 0:
        print(f"  {YELLOW}No differences detected — check the patterns!{RESET}")
    else:
        print(f"\n  {BOLD}{GREEN}✓ {changes} line(s) were scrubbed successfully.{RESET}")
        print(f"  {BOLD}{GREEN}  Sensitive data will NOT reach OpenAI.{RESET}")

    _banner("Done")


if __name__ == "__main__":
    main()
