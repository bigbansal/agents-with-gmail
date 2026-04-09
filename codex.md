# Gmail Skill for Codex

This project is a Codex skill. Invoke it by typing `$gmail` in the Codex composer.

## Install

```bash
python install_skill.py
```

This copies the skill into `~/.codex/skills/gmail/`, creates a Python venv,
and installs all dependencies.

## Setup (one time)

1. Edit `~/.codex/skills/gmail/.env` → add `OPENAI_API_KEY=sk-...`
2. Place your Google OAuth JSON at `~/.codex/skills/gmail/config/credentials.json`
   - Download from [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → Create OAuth 2.0 Client ID → Desktop app
3. First call of `$gmail` opens a browser once for Gmail consent, then runs silently.

## Usage in Codex

Type `$gmail` or describe your Gmail task naturally:

- "Give me a summary of today's emails"
- "Send an email to alice@example.com saying the meeting is at 3pm"
- "What are my unread emails?"
- "Summarise the PDF attachment in Bob's email"
- "Reply to Sarah saying I'll review by Friday"
- "Search for emails from my boss this week"

## Available actions

| Action | Description |
|---|---|
| `send_email` | Send email (`to`, `subject`, `body`) |
| `read_email` | Read one email by ID |
| `search_emails` | Gmail query search |
| `list_unread` | List unread inbox messages |
| `summarize_email` | AI summary of email + attachments |
| `day_summary` | Daily inbox briefing (categorised) |
| `read_attachment` | Extract PDF / Excel / CSV text |
| `reply_email` | Reply to a thread |
| `mark_read` | Mark messages as read |
| `delete_email` | Move to trash |

## File structure

```
skills/gmail_skill.py       ← GmailSkill class (all 10 actions)
skills/utils/gmail_auth.py  ← OAuth2 (token auto-cached after first login)
skills/utils/email_parser.py← MIME parsing, HTML→text, attachment metadata
skills/utils/attachment_reader.py ← PDF (pdfplumber) + Excel/CSV (pandas)
skills/utils/summarizer.py  ← OpenAI GPT-4o summaries
agent.py                    ← standalone interactive agent
SKILL.md                    ← Codex skill manifest
```
