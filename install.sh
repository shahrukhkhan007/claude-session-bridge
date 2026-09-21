#!/usr/bin/env bash
# One-command installer for claude-session-bridge (macOS / Linux).
# On Windows, run the script with Python directly (see the README).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/shahrukhkhan007/claude-session-bridge/main/install.sh | bash
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/shahrukhkhan007/claude-session-bridge/main"
BIN_DIR="$HOME/.local/bin"
SCRIPT_PATH="$BIN_DIR/claude-bridge"

echo "Installing claude-session-bridge…"

# 1. Requirements
case "$(uname -s)" in
  Darwin|Linux) ;;
  *)
    echo "This installer is for macOS/Linux. On Windows, run the script with" >&2
    echo "Python directly: python claude_session_bridge.py  (see the README)." >&2
    exit 1 ;;
esac
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install it (macOS: 'brew install python'; Linux: your" >&2
  echo "package manager, e.g. 'sudo apt install python3') and re-run." >&2
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

# 3. Make sure ~/.local/bin is on PATH (append to the right shell rc)
case "$(basename "${SHELL:-}")" in
  zsh)  SHELL_RC="$HOME/.zshrc" ;;
  bash) SHELL_RC="$HOME/.bashrc" ;;
  *)    SHELL_RC="$HOME/.profile" ;;
esac
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  {
    echo ""
    echo '# claude-session-bridge'
    echo 'export PATH="$HOME/.local/bin:$PATH"'
  } >> "$SHELL_RC"
  echo "Added $BIN_DIR to PATH in $SHELL_RC (open a new terminal to pick it up)."
fi

echo ""
echo "Installed. Command: claude-bridge"
echo "  claude-bridge            # dry run (safe, writes nothing)"
echo "  claude-bridge --apply    # register sessions into the current account"
echo "  claude-bridge --undo     # show latest backup for restore"
echo ""
echo "First run a dry run to check it sees your sessions correctly."
