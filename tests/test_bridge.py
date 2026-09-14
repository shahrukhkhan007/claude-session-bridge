#!/usr/bin/env python3
"""
End-to-end tests for claude_session_bridge.

Each test builds a synthetic HOME that mimics the Claude desktop app's on-disk
layout, then runs the real script as a subprocess with HOME pointed at it — the
same way a user runs it — and asserts on the resulting files and output. No
network, no real Claude data, no third-party dependencies (stdlib unittest).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "claude_session_bridge.py"

RICH_FIELDS = {
    "effort": "high", "permissionMode": "auto", "classifierSummaryEnabled": True,
    "chromePermissionMode": "skip_all_permission_checks", "completedTurns": 1,
    "enabledMcpTools": {}, "remoteMcpServersConfig": [], "titleSource": "auto",
}


def run(home, *args):
    """Run the script with a given fake HOME; return (exit_code, stdout+stderr)."""
    env = dict(os.environ, HOME=str(home))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env=env, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


class Fixture:
    """Builds a fake HOME with app-support index folders and CLI transcripts."""

    def __init__(self, root: Path):
        self.home = root
        self.app = root / "Library" / "Application Support" / "Claude"
        self.sessions = self.app / "claude-code-sessions"
        self.projects = root / ".claude" / "projects"
        self.sessions.mkdir(parents=True)
        self.projects.mkdir(parents=True)

    def set_account(self, acct):
        (self.app / "config.json").write_text(json.dumps({"lastKnownAccountUuid": acct}))

    def index_dir(self, acct, workspace):
        d = self.sessions / acct / workspace
        d.mkdir(parents=True, exist_ok=True)
        return d

    def registration(self, index_dir, sid, cli, title, rich=True, **extra):
        data = {
            "sessionId": f"local_{sid}", "cliSessionId": cli, "title": title,
            "createdAt": 1788000000000, "lastActivityAt": 1788000001000,
            "lastFocusedAt": 1788000001000, "cwd": "/Users/x/proj",
            "originCwd": "/Users/x/proj", "model": "claude-opus-5",
            "isArchived": False,
        }
        if rich:
            data.update(RICH_FIELDS)
        data.update(extra)
        (index_dir / f"local_{sid}.json").write_text(json.dumps(data))
        return data

    def transcript(self, project, cli, first_user_text, cwd="/Users/x/proj",
                   prepend_system_reminder=False):
        pdir = self.projects / project
        pdir.mkdir(parents=True, exist_ok=True)
        lines = []
        if prepend_system_reminder:
            lines.append(json.dumps({
                "type": "user", "uuid": "u0", "timestamp": "2026-09-01T10:00:00Z",
                "cwd": cwd,
                "message": {"role": "user",
                            "content": "<system-reminder>ignore this</system-reminder>"},
            }))
        lines.append(json.dumps({
            "type": "user", "uuid": "u1", "timestamp": "2026-09-01T10:00:05Z",
            "cwd": cwd,
            "message": {"role": "user", "content": first_user_text},
        }))
        lines.append(json.dumps({
            "type": "assistant", "uuid": "a1",
            "message": {"role": "assistant", "model": "claude-opus-5",
                        "content": [{"type": "text", "text": "ok"}]},
        }))
        (pdir / f"{cli}.jsonl").write_text("\n".join(lines) + "\n")

    def regs_in(self, index_dir):
        return list(index_dir.glob("local_*.json"))

    def load_regs(self, index_dir):
        return [json.loads(f.read_text()) for f in self.regs_in(index_dir)]


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    # ------------------------------------------------------------------ apply

    def test_dry_run_writes_nothing(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        self.fx.registration(idx, "seed", "seed-cli", "Seed")
        self.fx.transcript("proj", "seed-cli", "Seed")
        self.fx.transcript("proj", "new-cli", "A brand new session")
        code, out = run(self.fx.home)  # no --apply
        self.assertEqual(code, 0)
        self.assertIn("Dry run only", out)
        self.assertEqual(len(self.fx.regs_in(idx)), 1)  # unchanged

    def test_apply_registers_missing(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        self.fx.registration(idx, "seed", "seed-cli", "Seed")
        self.fx.transcript("proj", "seed-cli", "Seed")
        self.fx.transcript("proj", "new-cli", "A brand new session")
        code, out = run(self.fx.home, "--apply")
        self.assertEqual(code, 0)
        clis = {r["cliSessionId"] for r in self.fx.load_regs(idx)}
        self.assertIn("new-cli", clis)

    def test_apply_is_idempotent(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        self.fx.registration(idx, "seed", "seed-cli", "Seed")
        self.fx.transcript("proj", "seed-cli", "Seed")
        self.fx.transcript("proj", "new-cli", "New")
        run(self.fx.home, "--apply")
        n_after_first = len(self.fx.regs_in(idx))
        code, out = run(self.fx.home, "--apply")
        self.assertIn("Nothing to do", out)
        self.assertEqual(len(self.fx.regs_in(idx)), n_after_first)

    def test_apply_borrows_rich_template_cross_account(self):
        # current account empty; a rich reg exists only in another account
        self.fx.set_account("empty")
        empty = self.fx.index_dir("empty", "ws1")
        other = self.fx.index_dir("other", "wsx")
        self.fx.registration(other, "rich", "rich-cli", "Rich", rich=True)
        self.fx.transcript("proj", "mine-cli", "My session")
        code, out = run(self.fx.home, "--apply")
        self.assertEqual(code, 0)
        regs = self.fx.load_regs(empty)
        self.assertEqual(len(regs), 1)
        self.assertIn("chromePermissionMode", regs[0])  # inherited rich schema

    def test_apply_no_cross_workspace_duplicate(self):
        # same session already registered in a SIBLING workspace of the account
        self.fx.set_account("acctA")
        ws1 = self.fx.index_dir("acctA", "ws1")
        ws2 = self.fx.index_dir("acctA", "ws2")
        self.fx.registration(ws2, "dup", "dup-cli", "Already here")
        self.fx.transcript("proj", "dup-cli", "Already here")
        code, out = run(self.fx.home, "--apply")
        self.assertEqual(code, 0)
        all_clis = [r["cliSessionId"]
                    for d in (ws1, ws2) for r in self.fx.load_regs(d)]
        self.assertEqual(all_clis.count("dup-cli"), 1)  # not duplicated

    # ---------------------------------------------------------------- titles

    def test_title_skips_system_reminder(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        self.fx.registration(idx, "seed", "seed-cli", "Seed")
        self.fx.transcript("proj", "seed-cli", "Seed")
        self.fx.transcript("proj", "sr-cli", "The real first message",
                           prepend_system_reminder=True)
        run(self.fx.home, "--apply")
        reg = next(r for r in self.fx.load_regs(idx) if r["cliSessionId"] == "sr-cli")
        self.assertEqual(reg["title"], "The real first message")
        self.assertNotIn("system-reminder", reg["title"])

    # --------------------------------------------------------------- refresh

    def test_refresh_upgrades_and_retitles(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        # a minimal, bad-title entry that points at a good transcript
        self.fx.registration(idx, "bad", "bad-cli", "<system-reminder>", rich=False)
        # a rich template somewhere for schema
        self.fx.registration(self.fx.index_dir("other", "wsx"), "t", "t-cli", "T", rich=True)
        self.fx.transcript("proj", "bad-cli", "Fix the login screen",
                           prepend_system_reminder=True)
        code, out = run(self.fx.home, "--refresh")
        self.assertEqual(code, 0)
        reg = self.fx.load_regs(idx)[0]
        self.assertEqual(reg["title"], "Fix the login screen")
        self.assertIn("chromePermissionMode", reg)  # upgraded to rich schema

    def test_refresh_covers_all_workspaces(self):
        self.fx.set_account("acctA")
        ws1 = self.fx.index_dir("acctA", "ws1")
        ws2 = self.fx.index_dir("acctA", "ws2")
        self.fx.registration(ws1, "b1", "c1", "<system-reminder>", rich=False)
        self.fx.registration(ws2, "b2", "c2", "<system-reminder>", rich=False)
        self.fx.registration(self.fx.index_dir("other", "wsx"), "t", "tc", "T", rich=True)
        self.fx.transcript("proj", "c1", "First real", prepend_system_reminder=True)
        self.fx.transcript("proj", "c2", "Second real", prepend_system_reminder=True)
        run(self.fx.home, "--refresh")
        t1 = self.fx.load_regs(ws1)[0]["title"]
        t2 = self.fx.load_regs(ws2)[0]["title"]
        self.assertEqual({t1, t2}, {"First real", "Second real"})

    # ---------------------------------------------------------------- dedupe

    def test_dedupe_consolidates(self):
        self.fx.set_account("acctA")
        ws1 = self.fx.index_dir("acctA", "ws1")
        ws2 = self.fx.index_dir("acctA", "ws2")
        # more registrations in ws2 -> it becomes the "keep" target
        self.fx.registration(ws1, "d1", "same-cli", "Dup copy 1")
        self.fx.registration(ws2, "d2", "same-cli", "Dup copy 2")
        self.fx.registration(ws2, "extra", "extra-cli", "Extra")
        code, out = run(self.fx.home, "--dedupe")
        self.assertEqual(code, 0)
        remaining = [r["cliSessionId"]
                     for d in (ws1, ws2) for r in self.fx.load_regs(d)]
        self.assertEqual(remaining.count("same-cli"), 1)

    # -------------------------------------------------------------- diagnose

    def test_diagnose_separates_local_and_cloud(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        # local: has a transcript
        self.fx.registration(idx, "loc", "local-cli", "Local")
        self.fx.transcript("proj", "local-cli", "Local")
        # cloud: no transcript on disk
        self.fx.registration(idx, "cld", "cloud-cli", "Cloud", branch="claude/x")
        code, out = run(self.fx.home, "--diagnose")
        self.assertEqual(code, 0)
        self.assertIn("bridgeable): 1", out)
        self.assertIn("elsewhere): 1", out)

    # ---------------------------------------------------------------- safety

    def test_apply_creates_backup(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        self.fx.registration(idx, "seed", "seed-cli", "Seed")
        self.fx.transcript("proj", "seed-cli", "Seed")
        self.fx.transcript("proj", "new-cli", "New")
        run(self.fx.home, "--apply")
        backups = self.fx.home / ".claude_session_bridge_backups"
        self.assertTrue(backups.is_dir() and any(backups.iterdir()))

    def test_never_touches_transcripts(self):
        self.fx.set_account("acctA")
        idx = self.fx.index_dir("acctA", "ws1")
        self.fx.registration(idx, "seed", "seed-cli", "Seed")
        self.fx.transcript("proj", "new-cli", "New")
        tpath = self.fx.projects / "proj" / "new-cli.jsonl"
        before = tpath.read_bytes()
        run(self.fx.home, "--apply")
        run(self.fx.home, "--refresh")
        self.assertEqual(tpath.read_bytes(), before)  # transcript unchanged


if __name__ == "__main__":
    unittest.main(verbosity=2)
