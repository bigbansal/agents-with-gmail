---
name: gmailai
display_name: Gmail-AI
version: 1.0.0
description: Send, read, search and summarise Gmail. Reads PDF and Excel attachments with AI summaries.
author: Gourav Bansal
invocation: $gmailAi
tags: [email, gmail, gmailai productivity, pdf, excel, attachments]
---

# Gmail-AI Skill

Use this skill to interact with Gmail — send mail, read mail, search your inbox, get AI summaries of emails and attachments (PDF, Excel, CSV).

## Setup (first time only)

Before invoking this skill, run the installer from the skill's directory:

```bash
bash ~/.codex/skills/gmail/install.sh
```

This will:
1. Create a Python virtual environment at `~/.codex/skills/gmail/.venv`
2. Install all dependencies (Google API client, OpenAI, pdfplumber, pandas, etc.)
3. Prompt you to add your keys to `~/.codex/skills/gmail/.env`

You also need:
- `~/.codex/skills/gmail/config/credentials.json` — download from [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → OAuth 2.0 Client ID (Desktop app)
- `OPENAI_API_KEY` set in `~/.codex/skills/gmail/.env`

On first use, a browser window opens once for Gmail OAuth consent. After that it runs silently.

---

## How to invoke

Type `$gmailAi` in the Codex composer, or just describe what you want — Codex will auto-select this skill when your prompt is about Gmail.

---

## What you can ask

| What you say | What happens |
|---|---|
| "Give me a summary of today's emails" | Fetches today's inbox, returns categorised AI briefing |
| "Send an email to alice@example.com saying the meeting is at 3pm" | Sends the email |
| "What are my unread emails?" | Lists unread messages with sender, subject, date |
| "Summarise the PDF in Bob's email" | Downloads attachment, extracts text, returns AI summary |
| "Reply to the email from Sarah saying I'll review by Friday" | Sends a reply to that thread |
| "Search for emails from my boss this week" | Gmail query search |
| "Show me the Excel attachment from the finance report email" | Parses spreadsheet into a readable table |
| "Mark all those as read" | Batch marks messages as read |
| "Trash the newsletter from yesterday" | Moves to trash |
| "Give me a summary of last Thursday's emails" | Day briefing for any date |

---

## Available actions

The skill exposes these actions via `skills/gmail_skill.py`:

- **send_email** — `to`, `subject`, `body`, `cc`, `bcc`
- **read_email** — `message_id`
- **search_emails** — `query`, `max_results`
- **list_unread** — `max_results`
- **summarize_email** — `message_id`, `include_attachments`
- **day_summary** — `date_str` (YYYY-MM-DD, default today)
- **read_attachment** — `message_id`, `filename`, `summarize`
- **reply_email** — `message_id`, `body`
- **mark_read** — `message_ids`
- **delete_email** — `message_id`

---

## Running the agent directly

```bash
cd ~/.codex/skills/gmail
source .venv/bin/activate
python agent.py
```

---

## Environment variables

Set these in `~/.codex/skills/gmail/.env`:

```
OPENAI_API_KEY=sk-...
GMAIL_CREDENTIALS_PATH=config/credentials.json
OPENAI_MODEL=gpt-4o
MAX_EMAILS_FOR_DAY_SUMMARY=20
MAX_PDF_PAGES=50
MAX_EXCEL_ROWS=500
```

---

## File structure

```
~/.codex/skills/gmail/
  SKILL.md                  ← this file (Codex reads it)
  agent.py                  ← interactive agent entrypoint
  install.sh                ← one-command setup
  requirements.txt
  .env                      ← your secrets (not in git)
  config/
    credentials.json        ← Google OAuth (not in git)
    token.json              ← auto-generated after first login
  skills/
    gmail_skill.py          ← GmailSkill class
    skill_manifest.json     ← tool schema
    utils/
      gmail_auth.py
      email_parser.py
      attachment_reader.py
      summarizer.py
```
