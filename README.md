# claude-session-bridge

[![CI](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/ci.yml)
[![CodeQL](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/codeql.yml/badge.svg)](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Make your **Claude Code desktop-app sessions visible across accounts** on the same Mac.

![How claude-session-bridge works](docs/how-it-works.svg)

If you run two Claude accounts on one machine — say work and personal — and
switch between them when one hits a usage limit, the desktop app only shows the
sessions of whichever account is logged in. The conversations themselves are
stored on disk with **no account tag**; only a small per-account "registration"
file decides what shows in the sidebar. This tool writes the missing
registrations so your **local** sessions appear under whichever account you're
logged into — no more copying notes into a handoff file every time you switch.

> **Cross-platform:** macOS, Windows, and Linux. The tool auto-detects the
> desktop app's data folder on each (macOS `~/Library/Application Support/Claude`,
> Windows `%APPDATA%\Claude`, Linux `~/.config/Claude`).

## What it can and can't do

| | |
|---|---|
| ✅ Local desktop/CLI sessions (conversation file on this Mac) | Bridged across accounts |
| ❌ Cloud / web ("remote") sessions | Content lives on Anthropic's servers, never on disk — cannot be bridged |
| ❌ Sessions on a *different* computer | Not synced automatically; the files would have to be copied over first |

## Install (one command — macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/shahrukhkhan007/claude-session-bridge/main/install.sh | bash
```

This installs a `claude-bridge` command into `~/.local/bin`. Open a new terminal
afterwards. (Prefer not to pipe to bash? Download `claude_session_bridge.py` and
run it directly with `python3` — it's a single standard-library file.)

### Windows

No bash installer — just run the script with Python (install once via
`winget install Python.Python.3`). From PowerShell, in the folder with the
script:

```powershell
python claude_session_bridge.py             # dry run (safe, writes nothing)
python claude_session_bridge.py --apply     # register (backs up first)
```

Everything else — flags, backups, `--diagnose`, `--refresh`, `--dedupe` — is
identical. Fully quit the Claude app (right-click the tray icon → Quit, or end it
in Task Manager) and reopen it to see changes.

Closing the window is **not** enough — the app keeps running in the tray with
its old session list. If Claude was installed from the **Microsoft Store**, its
data lives in `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude`;
the tool finds it automatically.

## Usage

Always start with the safe preview (the default — it writes nothing):

```bash
claude-bridge                 # DRY RUN: lists sessions missing from this account
claude-bridge --apply         # register them (takes a backup first)
```

Log into the account you want the sessions to appear in **before** running
`--apply` — the script writes into whatever account is currently logged in.
Fully quit the app (**Cmd+Q**) and reopen it to see the changes.

### All options

| Command | What it does | Writes? |
|---|---|---|
| `claude-bridge` | Dry run. Lists sessions on disk that are missing from the current account's sidebar. | No |
| `claude-bridge --apply` | Registers the missing local sessions. Backs up the index first. | Adds only |
| `claude-bridge --refresh` | Rewrites this account's registrations with the full field schema and fixes junk titles (re-reads the transcript to recover the real first message). | Rewrites |
| `claude-bridge --dedupe` | If the same session got registered in more than one of the account's workspaces, keeps one copy and moves the extras to a backup. | Moves |
| `claude-bridge --diagnose` | Read-only report: where every account's sessions are stored, and how many are bridgeable vs cloud-only. | No |
| `claude-bridge --project <text>` | Limit to sessions whose project folder name contains `<text>`. | — |
| `claude-bridge --index-dir <path>` | Target a specific account's index folder instead of auto-detecting. | — |
| `claude-bridge --app-support <path>` | Target a specific instance's data dir (e.g. a `--user-data-dir` instance like `~/Library/Application Support/Claude-Work`) instead of the default. | — |
| `claude-bridge --projects-dir <path>` | Use a non-default transcripts dir (when an instance isolates its own transcripts). | — |
| `claude-bridge --include-deleted` | Also register sessions you deleted in the app (skipped by default). | — |
| `claude-bridge --undo` | Shows the latest backup for manual restore. | No |

### Typical fix-up

If the sidebar ever looks messy (duplicates, or `<system-reminder>` titles from
an older version):

```bash
claude-bridge --dedupe        # then
claude-bridge --refresh       # then quit + reopen the app
```

## Is it safe?

Yes — safety was the design priority:

- **Never touches your conversations.** It only *reads* the transcript files in
  `~/.claude/projects/`, never writes or deletes them.
- **Only adds or moves** registration pointers; it never overwrites or deletes
  an existing one (dedupe *moves* extras to a backup).
- **Backs up** the index folder before any change; `--undo` points you to it.
- **No network, no credentials.** It never opens your login token or contacts
  any server. Verify for yourself — it's ~500 lines of standard-library Python.

Worst case is a sidebar entry that looks off, fixable with `--undo`; your actual
conversations are never modified.

## How it works

The desktop app shows a session only if a small `local_*.json` registration
exists in that account's `claude-code-sessions/<account>/<workspace>/` index
folder. The transcripts in `~/.claude/projects/*.jsonl` are shared by the CLI,
the VS Code extension, and the desktop app, and carry no account binding. This
tool scans those transcripts and writes the missing registrations for the
current account, copying the field schema from an existing registration (from
any account) so the app renders them correctly.

## Caveats

- Relies on an **undocumented internal format** that a desktop-app update can
  change. Your transcripts are safe regardless; worst case the tool needs a
  small update.
- Only surfaces **local** sessions — cloud/web sessions have no file on disk.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests build synthetic fixtures and run the script as a subprocess — no real
Claude data, no network, no dependencies. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
