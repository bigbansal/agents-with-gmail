"""
agent.py – Codex Gmail Agent

An interactive agent powered by OpenAI function-calling that lets you
talk to Gmail in plain English.

Run:
    python agent.py

Example prompts:
    "Give me a summary of today's emails"
    "Send an email to alice@example.com saying the meeting is at 3 pm"
    "What are my unread emails?"
    "Summarise the PDF attachment in the last email from Bob"
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

load_dotenv()

# ── Add project root to sys.path so `skills` is importable ───────────────────
sys.path.insert(0, os.path.dirname(__file__))
from skills.gmail_skill import GmailSkill  # noqa: E402
from skills.utils.guardrails import scrub_messages, scrub_text  # noqa: E402

console = Console()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Build OpenAI tool definitions from the skill manifest ─────────────────────

def _build_tools(skill: GmailSkill) -> list[dict]:
    import json as _json
    from pathlib import Path

    manifest_path = Path(__file__).parent / "skills" / "skill_manifest.json"
    manifest = _json.loads(manifest_path.read_text())

    tools = []
    for action in manifest["actions"]:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": action["name"],
                    "description": action["description"],
                    "parameters": action["parameters"],
                },
            }
        )
    return tools


# ── Tool call executor ────────────────────────────────────────────────────────

def _execute_tool(skill: GmailSkill, name: str, args: dict) -> str:
    """Dispatch a tool call and serialise the result to a JSON string."""
    try:
        result = skill.run(name, **args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── Agent loop ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful personal email assistant with access to the user's Gmail account.

You can:
- Send, read, search, reply to and delete emails
- List unread messages
- Summarise individual emails including their PDF and Excel attachments
- Produce a daily briefing of the inbox
- Classify email sentiment (POSITIVE, NEGATIVE, COMPLIANCE, NEUTRAL)
- Auto-respond to emails based on sentiment using built-in templates
- Scan a batch of emails and auto-reply to negative, positive and compliance-related ones

When asked to auto-respond or auto-trigger replies:
  1. Use classify_email_sentiment to check the sentiment of specific emails.
  2. Use auto_respond_email to analyse and reply to a single email.
  3. Use auto_respond_scan to scan multiple emails and auto-reply in bulk.
  You can use dry_run=true to preview what would be sent before actually sending.

Always be concise and helpful. When listing emails, show the sender, subject and date.
When asked for a summary or briefing, use the summarize_email or day_summary tools.
Always confirm before sending or deleting emails by restating the key details.
Today's date is available via the day_summary tool (pass no arguments for today's summary).
"""


def run_agent():
    console.print(
        Panel.fit(
            "[bold cyan]Codex Gmail Agent[/bold cyan]\n"
            "[dim]Powered by OpenAI + Gmail API[/dim]\n"
            "Type [bold]exit[/bold] or [bold]quit[/bold] to stop.",
            border_style="cyan",
        )
    )

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    skill = GmailSkill()
    tools = _build_tools(skill)

    conversation: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if user_input.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Scrub user input before it enters the conversation
        conversation.append({"role": "user", "content": scrub_text(user_input)})

        # ── Agentic loop: keep calling OpenAI until no more tool calls ─────────
        while True:
            with console.status("[dim]Thinking …[/dim]", spinner="dots"):
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=scrub_messages(conversation),  # guardrail: scrub before sending
                    tools=tools,
                    tool_choice="auto",
                )

            choice = response.choices[0]
            msg = choice.message

            # Add assistant message (may include tool_calls)
            conversation.append(msg.model_dump(exclude_unset=True))

            # No tool calls → final answer
            if not msg.tool_calls:
                answer = msg.content or ""
                console.print()
                console.print(
                    Panel(
                        Markdown(answer),
                        title="[bold blue]Assistant[/bold blue]",
                        border_style="blue",
                    )
                )
                break

            # Execute each tool call and feed results back
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments or "{}")

                console.print(
                    f"  [dim]→ Calling tool:[/dim] [cyan]{fn_name}[/cyan] "
                    f"[dim]{json.dumps(fn_args, ensure_ascii=False)[:120]}[/dim]"
                )

                with console.status(f"[dim]Running {fn_name} …[/dim]", spinner="dots"):
                    tool_result = _execute_tool(skill, fn_name, fn_args)

                # Scrub tool result (email content) before storing in conversation
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": scrub_text(tool_result),
                    }
                )


def main():
    run_agent()


if __name__ == "__main__":
    main()
