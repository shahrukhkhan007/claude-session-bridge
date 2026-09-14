#!/usr/bin/env bash
# One-command installer for claude-session-bridge (macOS).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/shahrukhkhan007/claude-session-bridge/main/install.sh | bash
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/shahrukhkhan007/claude-session-bridge/main"
BIN_DIR="$HOME/.local/bin"
SCRIPT_PATH="$BIN_DIR/claude-bridge"

echo "Installing claude-session-bridge…"

# 1. Requirements
if [[ "$(uname)" != "Darwin" ]]; then
  echo "This installer targets macOS. Aborting." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install it (e.g. 'brew install python') and re-run." >&2
  exit 1
fi

# 2. Fetch the script into ~/.local/bin/claude-bridge
mkdir -p "$BIN_DIR"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$REPO_RAW/claude_session_bridge.py" -o "$SCRIPT_PATH"
else
  echo "curl not found." >&2; exit 1
fi
chmod +x "$SCRIPT_PATH"

# 3. Make sure ~/.local/bin is on PATH
SHELL_RC="$HOME/.zshrc"
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  echo "" >> "$SHELL_RC"
  echo '# claude-session-bridge' >> "$SHELL_RC"
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
  echo "Added $BIN_DIR to PATH in $SHELL_RC (open a new terminal to pick it up)."
fi

echo ""
echo "Installed. Command: claude-bridge"
echo "  claude-bridge            # dry run (safe, writes nothing)"
echo "  claude-bridge --apply    # register sessions into the current account"
echo "  claude-bridge --undo     # show latest backup for restore"
echo ""
echo "First run a dry run to check it sees your sessions correctly."
