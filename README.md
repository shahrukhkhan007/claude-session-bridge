# claude-session-bridge

[![CI](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/ci.yml)
[![CodeQL](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/codeql.yml/badge.svg)](https://github.com/shahrukhkhan007/claude-session-bridge/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Make your **Claude Code desktop-app sessions visible across accounts** on the same Mac.

If you run two Claude accounts on one machine — say work and personal — and
switch between them when one hits a usage limit, the desktop app only shows the
sessions of whichever account is logged in. The conversations themselves are
stored on disk with **no account tag**; only a small per-account "registration"
file decides what shows in the sidebar. This tool writes the missing
registrations so your **local** sessions appear under whichever account you're
logged into — no more copying notes into a handoff file every time you switch.

> **macOS only** for now. Windows uses a different storage layout (see
> [issues](https://github.com/shahrukhkhan007/claude-session-bridge/issues) —
> contributions welcome).

## What it can and can't do

| | |
|---|---|
| ✅ Local desktop/CLI sessions (conversation file on this Mac) | Bridged across accounts |
| ❌ Cloud / web ("remote") sessions | Content lives on Anthropic's servers, never on disk — cannot be bridged |
| ❌ Sessions on a *different* computer | Not synced automatically; the files would have to be copied over first |

## Install (one command, macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/shahrukhkhan007/claude-session-bridge/main/install.sh | bash
```

This installs a `claude-bridge` command into `~/.local/bin`. Open a new terminal
afterwards. (Prefer not to pipe to bash? Download `claude_session_bridge.py` and
run it directly with `python3` — it's a single standard-library file.)

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
