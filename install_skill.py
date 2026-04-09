"""
install_skill.py – installs the Gmail skill into the Codex skills directory.

Usage:
    python install_skill.py

What it does:
  1. Copies this project into ~/.codex/skills/gmail/
  2. Installs Python dependencies into ~/.codex/skills/gmail/.venv
  3. Sets up .env from .env.example if missing
  4. Checks for Google OAuth credentials
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

SKILL_SRC = Path(__file__).parent
SKILL_NAME = "gmail"
CODEX_SKILLS_DIR = Path(os.getenv("CODEX_SKILLS_DIR", Path.home() / ".codex" / "skills"))
SKILL_DEST = CODEX_SKILLS_DIR / SKILL_NAME


def step(msg: str) -> None:
    print(f"\n▶  {msg}")

def ok(msg: str) -> None:
    print(f"   ✓ {msg}")

def warn(msg: str) -> None:
    print(f"   ⚠  {msg}", file=sys.stderr)

def fail(msg: str) -> None:
    print(f"   ✗ {msg}", file=sys.stderr)
    sys.exit(1)


# ── 1. Copy skill files into ~/.codex/skills/gmail/ ──────────────────────────

def _ignore(src: str, names: list) -> set:
    ignored: set = set()
    for name in names:
        if name in {".venv", "__pycache__", ".git", ".DS_Store", "dist", "build"}:
            ignored.add(name)
        if name.endswith(".pyc"):
            ignored.add(name)
        # Never copy a cached OAuth token to the destination
        if name == "token.json" and "config" in src:
            ignored.add(name)
    return ignored


def copy_skill():
    step(f"Copying skill to {SKILL_DEST} …")
    # Preserve existing secrets across reinstalls
    env_backup = creds_backup = token_backup = None
    if SKILL_DEST.exists():
        env_file = SKILL_DEST / ".env"
        creds_file = SKILL_DEST / "config" / "credentials.json"
        token_file = SKILL_DEST / "config" / "token.json"
        if env_file.exists():
            env_backup = env_file.read_text()
        if creds_file.exists():
            creds_backup = creds_file.read_bytes()
        if token_file.exists():
            token_backup = token_file.read_bytes()
        shutil.rmtree(SKILL_DEST)

    shutil.copytree(str(SKILL_SRC), str(SKILL_DEST), ignore=_ignore)

    if env_backup:
        (SKILL_DEST / ".env").write_text(env_backup)
        ok("Preserved existing .env")
    if creds_backup:
        p = SKILL_DEST / "config" / "credentials.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(creds_backup)
        ok("Preserved existing credentials.json")
    if token_backup:
        p = SKILL_DEST / "config" / "token.json"
        p.write_bytes(token_backup)
        ok("Preserved existing token.json")

    ok(f"Skill installed to {SKILL_DEST}")


# ── 2. Install Python dependencies into the skill's own venv ─────────────────

def install_dependencies():
    step("Installing Python dependencies into skill venv …")
    venv_dir = SKILL_DEST / ".venv"
    pip = venv_dir / "bin" / "pip"

    if not venv_dir.exists():
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            fail(f"Failed to create venv: {result.stderr}")

    result = subprocess.run(
        [str(pip), "install", "-r", str(SKILL_DEST / "requirements.txt"), "-q"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        fail(f"pip install failed:\n{result.stderr}")
    ok("Dependencies installed in skill venv.")


# ── 3. Set up .env ────────────────────────────────────────────────────────────

def setup_env():
    step("Checking .env configuration …")
    env_dest = SKILL_DEST / ".env"
    env_example = SKILL_DEST / ".env.example"
    if not env_dest.exists() and env_example.exists():
        shutil.copy2(env_example, env_dest)
        warn(f"Created .env at {env_dest}\n"
             "   → Open it and set OPENAI_API_KEY=sk-...")
    elif env_dest.exists():
        ok(".env already exists and was preserved.")


# ── 4. Check Gmail credentials ────────────────────────────────────────────────

def check_credentials():
    step("Checking Gmail OAuth credentials …")
    creds = SKILL_DEST / "config" / "credentials.json"
    (SKILL_DEST / "config").mkdir(parents=True, exist_ok=True)
    if not creds.exists():
        warn(
            f"Missing: {creds}\n"
            "   Download from:\n"
            "   https://console.cloud.google.com → APIs & Services\n"
            "   → Credentials → Create OAuth 2.0 Client ID → Desktop app\n"
            f"   → Save as: {creds}"
        )
    else:
        ok(f"Found credentials.json")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Codex Gmail Skill – Installer")
    print("=" * 60)

    copy_skill()
    install_dependencies()
    setup_env()
    check_credentials()

    print("\n" + "=" * 60)
    print("  Installation complete!")
    print()
    print(f"  Skill installed to:  {SKILL_DEST}")
    print()
    print("  Next steps:")
    print(f"  1. Edit {SKILL_DEST / '.env'}")
    print("     → Add: OPENAI_API_KEY=sk-...")
    print(f"  2. Place credentials.json at:")
    print(f"     {SKILL_DEST / 'config' / 'credentials.json'}")
    print()
    print("  Then in Codex, type:  $gmail")
    print("  Or run the agent:     python ~/.codex/skills/gmail/agent.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
