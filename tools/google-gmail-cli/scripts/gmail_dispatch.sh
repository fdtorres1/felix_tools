#!/bin/zsh
set -euo pipefail

# Ensure env and venv
export AGENTS_ENV_PATH="$HOME/AGENTS.env"
if [ -f "$HOME/.venvs/codex-tools/bin/activate" ]; then
  source "$HOME/.venvs/codex-tools/bin/activate"
fi

"$HOME/.codex/tools/gmail.py" queue dispatch --max 20 >> "$HOME/.codex/tools/gmail_outbox/dispatch.log" 2>&1 || true

