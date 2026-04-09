#!/usr/bin/env bash
# install.sh – installs the Gmail skill into the Codex skills directory.
#
# Usage:
#   bash install.sh
#
# Also runs automatically from inside Codex when the skill is invoked
# for the first time via $gmail.

set -euo pipefail

SKILL_DEST="${CODEX_SKILLS_DIR:-$HOME/.codex/skills}/gmail"

echo "========================================"
echo "  Codex Gmail Skill – Installer"
echo "========================================"

# 1. Run the Python installer (copies files, creates venv, installs deps)
echo ""
echo "▶  Running skill installer …"
python3 "$(dirname "$0")/install_skill.py"

# 2. Remind the user about config (installer already printed this,
#    but repeat for clarity if run standalone)
echo ""
echo "========================================"
echo "  Quick reference:"
echo ""
echo "  Edit:    $SKILL_DEST/.env"
echo "           → Add: OPENAI_API_KEY=sk-..."
echo ""
echo "  Place:   $SKILL_DEST/config/credentials.json"
echo "           Download from: https://console.cloud.google.com"
echo "           → APIs & Services → Credentials"
echo "           → Create OAuth 2.0 Client ID → Desktop app → Download"
echo ""
echo "  Then in Codex type:  \$gmail"
echo "  Or run directly:     python ~/.codex/skills/gmail/agent.py"
echo "========================================"
