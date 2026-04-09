# Codex Gmail Skill

Talk to your Gmail inbox in plain English, powered by **OpenAI GPT-4o** and the **Gmail API**.

---

## Features

| Capability | Description |
|---|---|
| **Send email** | Compose and send email to any address |
| **Read email** | Fetch and display any message by ID |
| **Search emails** | Full Gmail query syntax (`is:unread`, `from:`, `subject:`, `after:`, …) |
| **List unread** | Instantly see what needs attention |
| **Reply** | Reply to any thread |
| **Delete / Trash** | Move messages to trash |
| **Summarise email** | AI-generated 2-4 sentence summary of any email |
| **Day summary** | Categorised daily briefing (Action Required / Updates / FYI / Promos) |
| **Read PDF** | Extract text & tables from PDF attachments (up to 50 pages) |
| **Read Excel / CSV** | Parse spreadsheets into readable tables (up to 500 rows) |
| **Summarise attachment** | AI summary of any PDF or Excel file in an email |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | `python3 --version` |
| OpenAI API key | [platform.openai.com](https://platform.openai.com/api-keys) |
| Google Cloud Project | [console.cloud.google.com](https://console.cloud.google.com) |
| Gmail API enabled | APIs & Services → Enable APIs → Gmail API |
| OAuth 2.0 Desktop credentials | Download as `config/credentials.json` |

---

## Quick Start

### 1. Clone and install

```bash
cd agents-with-gmail
bash install.sh
```

`install.sh` will:
- Create a Python virtual environment `.venv`
- Install all dependencies from `requirements.txt`
- Register the Gmail skill with Codex (`~/.codex/skills/`)
- Guide you through any missing configuration

### 2. Set environment variables

```bash
cp .env.example .env
# Open .env and fill in:
#   OPENAI_API_KEY=sk-...
```

### 3. Add Gmail OAuth credentials

1. Open [Google Cloud Console](https://console.cloud.google.com)
2. Create (or select) a project
3. Enable the **Gmail API** under APIs & Services
4. Go to **Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Set **Application type** to **Desktop app**
6. Click Download and save the file as **`config/credentials.json`**

### 4. Run the agent

```bash
source .venv/bin/activate
python agent.py
```

On first run a browser window will open for Gmail authorisation consent.
After approval, `config/token.json` is saved and future runs are silent.

---

## Example Conversations

```
You: Give me a summary of today's emails
Assistant: Here is your daily briefing for April 9, 2026 ...

You: Send an email to alice@example.com with subject "Meeting notes" and body "Hi Alice, ..."
Assistant: I'll send that email now. To: alice@example.com, Subject: Meeting notes. Shall I proceed?

You: What are my unread emails?
Assistant: You have 4 unread emails: ...

You: Summarise the PDF attachment in the email from Bob
Assistant: The PDF "Q1_Report.pdf" attached to Bob's email contains ...

You: Reply to message 18b2c3d4 saying "Thanks, I'll review by Friday"
Assistant: Reply sent successfully.
```

---

## Project Structure

```
agents-with-gmail/
├── agent.py                    # Interactive Codex agent (run this)
├── install_skill.py            # Codex skill registration script
├── install.sh                  # One-shot bash installer
├── setup.py                    # pip-installable package definition
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── config/
│   ├── credentials.json        # ← place your Google OAuth file here
│   └── token.json              # auto-generated after first auth
└── skills/
    ├── __init__.py
    ├── gmail_skill.py          # GmailSkill class (10 actions)
    ├── skill_manifest.json     # Codex skill descriptor
    └── utils/
        ├── __init__.py
        ├── gmail_auth.py       # OAuth2 helper
        ├── email_parser.py     # MIME parsing, attachment metadata
        ├── attachment_reader.py# PDF / Excel / CSV extraction
        └── summarizer.py       # OpenAI-backed summaries
```

---

## Skill Actions Reference

| Action | Key Parameters | Description |
|---|---|---|
| `send_email` | `to`, `subject`, `body` | Send a new email |
| `read_email` | `message_id` | Read one email by ID |
| `search_emails` | `query`, `max_results` | Gmail query search |
| `list_unread` | `max_results` | Show unread inbox messages |
| `summarize_email` | `message_id`, `include_attachments` | AI summary of email + attachments |
| `day_summary` | `date_str` (YYYY-MM-DD) | Daily inbox briefing |
| `read_attachment` | `message_id`, `filename`, `summarize` | Extract PDF/Excel/CSV text |
| `reply_email` | `message_id`, `body` | Reply to a thread |
| `mark_read` | `message_ids` | Mark messages as read |
| `delete_email` | `message_id` | Trash a message |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI key |
| `OPENAI_MODEL` | `gpt-4o` | Model used for all summaries |
| `GMAIL_CREDENTIALS_PATH` | `config/credentials.json` | Path to Google OAuth JSON |
| `GMAIL_TOKEN_PATH` | `config/token.json` | Where the access token is cached |
| `GMAIL_SCOPES` | `https://…/gmail.modify` | Gmail OAuth scope |
| `MAX_EMAILS_FOR_DAY_SUMMARY` | `20` | Max emails fetched for day summary |
| `MAX_PDF_PAGES` | `50` | Max PDF pages parsed per file |
| `MAX_EXCEL_ROWS` | `500` | Max Excel rows read per file |

---

## Security Notes

- `config/credentials.json` and `config/token.json` are **never** committed to git (add them to `.gitignore`).
- The OAuth scope `gmail.modify` allows reading, sending and trashing; it does **not** permanently delete emails.
- All AI processing uses the OpenAI API; email content is sent to OpenAI for summarisation.
