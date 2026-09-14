#!/usr/bin/env python3
"""
claude_session_bridge.py — make Claude (Code) desktop-app sessions from one
account visible in another account's sidebar, on the SAME Mac.

How it works
------------
The desktop app shows only sessions that have a small registration JSON in an
account-specific index folder (".../claude-code-sessions.../local_*.json").
The conversation transcripts themselves (~/.claude/projects/**/*.jsonl) are
NOT account-bound. This script scans transcripts on disk and writes missing
registration files into the CURRENTLY LOGGED-IN account's index folder, using
one of that account's existing registrations as a field template.

Safety
------
- Default mode is a DRY RUN: prints what it would do, writes nothing.
- `--apply` creates a timestamped backup of the index folder before writing.
- Reads only: transcript metadata (first lines) and index JSONs. No network.
- Quit the Claude desktop app fully before running with --apply.

Usage
-----
  python3 claude_session_bridge.py                # discover + dry run
  python3 claude_session_bridge.py --apply        # actually register
  python3 claude_session_bridge.py --apply --project my-app   # filter
  python3 claude_session_bridge.py --undo         # restore latest backup

No dependencies beyond the Python 3 standard library.
"""

import argparse
import json
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
APP_SUPPORT_CANDIDATES = [
    HOME / "Library" / "Application Support" / "Claude",
    HOME / "Library" / "Application Support" / "Claude Code",
]
CLI_PROJECTS = HOME / ".claude" / "projects"
BACKUP_ROOT = HOME / ".claude_session_bridge_backups"


def log(msg=""):
    print(msg)


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- discovery

def find_app_support():
    for p in APP_SUPPORT_CANDIDATES:
        if p.is_dir():
            return p
    fail("Could not find the Claude desktop app data folder under "
         "~/Library/Application Support. Is the desktop app installed?")


def find_session_index_dirs(app_support):
    """Return every directory that holds local_*.json registrations.

    Known layouts (varies by app version):
      .../claude-code-sessions/<accountUuid>/<orgUuid>/local_*.json
      .../claude-code-sessions-<accountUuid>-<workspaceUuid>/local_*.json
    We discover instead of assuming: any dir under app_support whose name
    starts with 'claude-code-sessions', walked up to 3 levels deep, that
    directly contains local_*.json files (or is a leaf directory).
    """
    roots = sorted(app_support.glob("claude-code-sessions*"))
    index_dirs = []
    for root in roots:
        if not root.is_dir():
            continue
        candidates = [root] + [d for d in root.glob("*/") ] + [d for d in root.glob("*/*/")]
        for d in candidates:
            if not d.is_dir():
                continue
            if list(d.glob("local_*.json")) or not any(c.is_dir() for c in d.iterdir()):
                index_dirs.append(d)
    # de-dup while keeping order
    seen, out = set(), []
    for d in index_dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return roots, out


def current_account_uuid(app_support):
    """Best effort: read the app config for the active account id."""
    for name in ("config.json", "Preferences", "settings.json"):
        p = app_support / name
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            for key in ("lastKnownAccountUuid", "accountUuid", "activeAccountUuid"):
                if isinstance(data, dict) and data.get(key):
                    return data[key], p
    return None, None


def load_registrations(index_dir):
    """Map cliSessionId -> registration path for one index dir."""
    regs = {}
    for f in index_dir.glob("local_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        cli_id = data.get("cliSessionId") or data.get("sessionId")
        if cli_id:
            regs[str(cli_id)] = f
    return regs


# ---------------------------------------------------------------- transcripts

def transcript_meta(jsonl_path, max_lines=200):
    """Extract session metadata from the first lines of a transcript."""
    meta = {
        "cliSessionId": jsonl_path.stem,
        "cwd": None,
        "title": None,
        "model": None,
        "createdAt": None,
        "lastActivityAt": int(jsonl_path.stat().st_mtime * 1000),
    }
    try:
        with jsonl_path.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                line = line.lstrip("﻿").strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if meta["cwd"] is None and entry.get("cwd"):
                    meta["cwd"] = entry["cwd"]
                if meta["createdAt"] is None and entry.get("timestamp"):
                    meta["createdAt"] = to_ms(entry["timestamp"])
                msg = entry.get("message") or {}
                if meta["model"] is None and isinstance(msg, dict) and msg.get("model"):
                    meta["model"] = msg["model"]
                if meta["title"] is None and entry.get("type") == "user":
                    text = extract_text(msg)
                    if text:
                        meta["title"] = text[:70]
                if all(meta[k] is not None for k in ("cwd", "title", "model", "createdAt")):
                    break
    except OSError as e:
        log(f"  ! could not read {jsonl_path.name}: {e}")
        return None
    if meta["createdAt"] is None:
        meta["createdAt"] = int(jsonl_path.stat().st_ctime * 1000)
    if not meta["title"]:
        meta["title"] = f"Recovered session {jsonl_path.stem[:8]}"
    return meta


def to_ms(ts):
    try:
        if isinstance(ts, (int, float)):
            return int(ts if ts > 1e12 else ts * 1000)
        return int(datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def clean_user_text(raw):
    """Turn a raw user message into a clean title candidate, or None.

    Strips injected <system-reminder>/<command-*> blocks and stray tags that
    Claude Code prepends, then returns the first real line of text.
    """
    if not raw:
        return None
    s = re.sub(r"<system-reminder>.*?</system-reminder>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<command-[^>]*>.*?</command-[^>]*>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)          # drop any remaining tags
    for line in s.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def extract_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return clean_user_text(c)
    if isinstance(c, list):
        parts = [p.get("text", "") for p in c
                 if isinstance(p, dict) and p.get("type") == "text"]
        return clean_user_text("\n".join(parts))
    return None


def scan_transcripts(project_filter=None):
    if not CLI_PROJECTS.is_dir():
        fail(f"No transcripts folder at {CLI_PROJECTS}. Nothing to register.")
    found = []
    for proj_dir in sorted(CLI_PROJECTS.iterdir()):
        if not proj_dir.is_dir():
            continue
        if project_filter and project_filter.lower() not in proj_dir.name.lower():
            continue
        for jsonl in sorted(proj_dir.glob("*.jsonl")):
            if jsonl.stat().st_size == 0:
                continue
            found.append(jsonl)
    return found


# ---------------------------------------------------------------- registration

def build_registration(template, meta):
    """New registration dict: template's schema, this session's values."""
    reg = dict(template) if template else {}
    now_ms = int(time.time() * 1000)
    reg.update({
        "sessionId": f"local_{uuid.uuid4()}",
        "cliSessionId": meta["cliSessionId"],
        "title": meta["title"],
        "createdAt": meta["createdAt"],
        "lastActivityAt": meta["lastActivityAt"],
        "lastFocusedAt": meta["lastActivityAt"] or now_ms,
        "isArchived": False,
    })
    cwd = meta["cwd"] or str(HOME)          # never borrow the template's cwd
    reg["cwd"] = cwd
    reg["originCwd"] = cwd
    if "workingDirectory" in reg:
        reg["workingDirectory"] = cwd
    if meta["model"]:
        reg["model"] = meta["model"]
    return reg


def best_template(index_dirs):
    """The richest existing registration across ALL accounts — used as the field
    schema when the target account has none of its own to copy."""
    best = None
    for d in index_dirs:
        for f in d.glob("local_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if best is None or len(data) > len(best):
                best = data
    return best


def existing_across(dirs):
    """Union of cliSessionIds already registered across several workspace dirs."""
    seen = {}
    for d in dirs:
        for cli, f in load_registrations(d).items():
            seen.setdefault(cli, f)
    return seen


def backup(index_dir):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_ROOT / stamp / index_dir.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(index_dir, dest)
    return dest


def undo():
    if not BACKUP_ROOT.is_dir():
        fail("No backups found — nothing to undo.")
    stamps = sorted(BACKUP_ROOT.iterdir())
    if not stamps:
        fail("No backups found — nothing to undo.")
    latest = stamps[-1]
    log(f"Latest backup: {latest}")
    log("To restore, quit the Claude app, then copy the backed-up folder back over "
        "the matching folder under ~/Library/Application Support/Claude/ .")
    log("(Automatic restore is intentionally manual so you stay in control.)")


# ---------------------------------------------------------------- diagnose

SKIP_VALUE_KEYS = {"title"}  # may contain personal text — show key only


def safe_fields(data):
    """Return 'key=value' strings, hiding conversation text and long/blob values."""
    out = []
    for k in sorted(data.keys()):
        v = data[k]
        if k in SKIP_VALUE_KEYS:
            out.append(f"{k}=<hidden>")
        elif isinstance(v, (dict, list)):
            out.append(f"{k}=<{type(v).__name__}>")
        elif isinstance(v, str) and len(v) > 60:
            out.append(f"{k}=<long>")
        else:
            out.append(f"{k}={v}")
    return out


def find_all_transcripts(app_support):
    """Every *.jsonl on disk that could be a session transcript, by location."""
    roots = {
        "~/.claude/projects": CLI_PROJECTS,
        "app-support": app_support,
        "~/.claude (other)": HOME / ".claude",
    }
    index = {}  # stem -> path
    locations = {}
    for label, root in roots.items():
        if not root.is_dir():
            continue
        count = 0
        for p in root.rglob("*.jsonl"):
            count += 1
            index.setdefault(p.stem, p)
        locations[label] = count
    return index, locations


def diagnose():
    app_support = find_app_support()
    log(f"App data folder : {app_support}\n")

    tindex, locations = find_all_transcripts(app_support)
    log("Transcript files on disk (*.jsonl), by location:")
    for label, n in locations.items():
        log(f"  {label:24s} {n}")
    log(f"  TOTAL distinct session ids on disk: {len(tindex)}\n")

    acct, _ = current_account_uuid(app_support)
    roots, index_dirs = find_session_index_dirs(app_support)
    log(f"Active account  : {acct or 'unknown'}\n")

    for d in index_dirs:
        regs = list(d.glob("local_*.json"))
        is_current = bool(acct and acct in str(d))
        label = "  <-- CURRENTLY LOGGED IN" if is_current else ""
        rel = d.relative_to(app_support)
        log(f"Index: {rel}{label}")
        log(f"  registrations: {len(regs)}")
        with_local, without_local = [], []
        for f in regs:
            try:
                data = json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            cli = str(data.get("cliSessionId") or data.get("sessionId") or "")
            (with_local if cli in tindex else without_local).append(data)
        log(f"  have a transcript on disk (bridgeable): {len(with_local)}")
        log(f"  no transcript on disk (cloud, or stored elsewhere): {len(without_local)}")
        if with_local:
            log(f"  EXAMPLE with transcript   : {' | '.join(safe_fields(with_local[0]))}")
        if without_local:
            log(f"  EXAMPLE without transcript: {' | '.join(safe_fields(without_local[0]))}")
        log()

    log("Reading: 'bridgeable' = a session whose conversation file exists on your")
    log("disk, so it can be shown under another account. Compare the two EXAMPLE")
    log("lines to see which field marks a cloud session. Nothing above was changed.")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Register on-disk Claude sessions "
                                 "into the current account's desktop sidebar.")
    ap.add_argument("--apply", action="store_true", help="write registrations (default: dry run)")
    ap.add_argument("--project", help="only sessions whose project folder name contains this text")
    ap.add_argument("--index-dir", help="explicit index folder to write into (overrides auto-pick)")
    ap.add_argument("--undo", action="store_true", help="show latest backup for manual restore")
    ap.add_argument("--diagnose", action="store_true",
                    help="inspect where every account's sessions are stored (read-only)")
    ap.add_argument("--refresh", action="store_true",
                    help="rewrite EXISTING registrations for this account using the richest "
                         "field schema found, and clean up bad titles")
    ap.add_argument("--dedupe", action="store_true",
                    help="consolidate sessions registered in more than one of this "
                         "account's workspaces (moves extra copies to a backup)")
    args = ap.parse_args()

    if args.undo:
        undo()
        return

    if args.diagnose:
        diagnose()
        return

    app_support = find_app_support()
    log(f"App data folder : {app_support}")

    acct, src = current_account_uuid(app_support)
    log(f"Active account  : {acct or 'unknown'}" + (f"  (from {src.name})" if src else ""))

    roots, index_dirs = find_session_index_dirs(app_support)
    if not roots:
        fail("No 'claude-code-sessions*' folder found. Open the desktop app once, "
             "start any throwaway session, quit it, and re-run.")
    log(f"Index folders   : {len(index_dirs)} found")
    for d in index_dirs:
        n = len(list(d.glob('local_*.json')))
        log(f"  - {d.relative_to(app_support)}  ({n} registrations)")

    # Treat the whole logged-in account as one unit: all its workspace folders.
    acct_dirs = [d for d in index_dirs if acct and acct in str(d)]
    if args.index_dir:
        target = Path(args.index_dir).expanduser()
        if not target.is_dir():
            fail(f"--index-dir {target} does not exist")
        acct_dirs = [target]
    elif acct_dirs:
        # primary = the workspace with the most registrations (ties: newest)
        target = max(acct_dirs, key=lambda d: (len(list(d.glob("local_*.json"))),
                                               d.stat().st_mtime))
    else:
        regs_dirs = [d for d in index_dirs if list(d.glob("local_*.json"))]
        if not regs_dirs:
            fail("No index folder with existing registrations. Start one session in the "
                 "desktop app under the CURRENT account first (it creates the folder and "
                 "gives this script a template), then re-run.")
        target = max(regs_dirs, key=lambda d: d.stat().st_mtime)
        acct_dirs = [target]

    rel_t = target.relative_to(app_support) if target.is_relative_to(app_support) else target
    log(f"Target index    : {rel_t}")
    if len(acct_dirs) > 1:
        log(f"  (this account has {len(acct_dirs)} workspace folders — handled together)")

    template = best_template(index_dirs)
    log(f"Template        : {'rich schema found' if template else 'NONE — none found anywhere'}")

    # --dedupe: a session registered in more than one of this account's
    # workspaces is a duplicate. Keep the copy in the target workspace, move the
    # rest into a backup folder (moved, not deleted).
    if args.dedupe:
        loc = {}
        for d in acct_dirs:
            for f in d.glob("local_*.json"):
                try:
                    cli = str(json.loads(f.read_text(encoding="utf-8-sig")).get("cliSessionId") or "")
                except Exception:
                    continue
                if cli:
                    loc.setdefault(cli, []).append(f)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dump = BACKUP_ROOT / stamp / "dedupe-removed"
        moved = 0
        for _cli, files in loc.items():
            if len(files) < 2:
                continue
            keep = next((f for f in files if f.parent == target), files[0])
            for f in files:
                if f == keep:
                    continue
                dump.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dump / f"{f.parent.name}__{f.name}"))
                moved += 1
        log(f"\nConsolidated duplicates: moved {moved} extra copies to\n  {dump}")
        log("Fully quit the Claude desktop app (Cmd+Q) and reopen it.")
        return

    # --refresh: rewrite existing registrations across ALL of this account's
    # workspaces with the rich schema, and clean up junk titles.
    if args.refresh:
        if not template:
            fail("--refresh needs a template registration to exist somewhere. Start one "
                 "normal session in any account first.")
        tindex, _ = find_all_transcripts(app_support)
        fixed = retitled = 0
        for d in acct_dirs:
            backup(d)
            for f in sorted(d.glob("local_*.json")):
                try:
                    cur = json.loads(f.read_text(encoding="utf-8-sig"))
                except Exception:
                    continue
                merged = dict(template)          # rich defaults
                merged.update(cur)               # keep this entry's real values
                for k in ("sessionId", "cliSessionId", "title", "createdAt",
                          "lastActivityAt", "lastFocusedAt", "cwd", "originCwd",
                          "model", "isArchived"):
                    if k in cur:
                        merged[k] = cur[k]
                title = str(cur.get("title") or "")
                if (not title) or title.startswith("<") or title.startswith("Recovered"):
                    cli = str(cur.get("cliSessionId") or cur.get("sessionId") or "")
                    tp = tindex.get(cli)
                    if tp:
                        m = transcript_meta(tp)
                        if m:
                            merged["title"] = m["title"]
                            merged["cwd"] = m["cwd"] or merged.get("cwd")
                            merged["originCwd"] = merged["cwd"]
                            retitled += 1
                f.write_text(json.dumps(merged, indent=2), encoding="utf-8")
                fixed += 1
        log(f"\nRefreshed {fixed} registrations across {len(acct_dirs)} workspace(s) "
            f"({retitled} re-titled from the transcript).")
        log("Fully quit the Claude desktop app (Cmd+Q) and reopen it.")
        return

    # For --apply: dedupe across ALL the account's workspaces so we never write a
    # session that's already registered in a sibling workspace.
    existing = existing_across(acct_dirs)

    transcripts = scan_transcripts(args.project)
    log(f"Transcripts     : {len(transcripts)} found under {CLI_PROJECTS}")

    todo = [t for t in transcripts if t.stem not in existing]
    log(f"Unregistered    : {len(todo)} for this account\n")

    if not todo:
        log("Nothing to do — every transcript is already in this account's sidebar.")
        return

    if args.apply:
        b = backup(target)
        log(f"Backup written  : {b}\n")

    written = 0
    for t in todo:
        meta = transcript_meta(t)
        if meta is None:
            continue
        reg = build_registration(template, meta)
        out = target / f"{reg['sessionId']}.json"
        stamp = datetime.fromtimestamp(meta['lastActivityAt']/1000).strftime('%Y-%m-%d %H:%M')
        if args.apply:
            out.write_text(json.dumps(reg, indent=2), encoding="utf-8")
            written += 1
            log(f"  + registered  [{stamp}]  {meta['title']!r}")
        else:
            log(f"  ~ would register  [{stamp}]  {meta['title']!r}  ({t.name})")

    log()
    if args.apply:
        log(f"Done: {written} sessions registered into {target.name}.")
        log("Fully quit the Claude desktop app (Cmd+Q) and reopen it to see them.")
    else:
        log(f"Dry run only — nothing written. Re-run with --apply to register "
            f"{len(todo)} sessions.")


if __name__ == "__main__":
    main()
