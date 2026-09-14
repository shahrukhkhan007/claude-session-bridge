# Contributing

Thanks for helping improve `claude-session-bridge`! This tool manipulates the
Claude desktop app's local data, so contributions are reviewed with a heavy bias
toward **safety and simplicity**.

## Ground rules

The tool must always:

- make **no network calls** and touch **no credentials**;
- treat conversation transcripts as **read-only**;
- **back up** before writing, and only **add/move** registration files;
- depend only on the **Python standard library** (no third-party runtime deps).

PRs that break any of these will be declined regardless of the feature.

## Development setup

No dependencies to install for the tool itself. To run the checks locally:

```bash
# tests (standard library only)
python3 -m unittest discover -s tests -v

# optional lint/security (matches CI)
pip install "ruff==0.6.*" "bandit==1.7.*"
ruff check .
bandit -r claude_session_bridge.py --severity-level medium
```

## Making a change

1. Fork and create a branch off `main`.
2. Add or update a test in `tests/test_bridge.py` for any behavior change. Tests
   build synthetic fixtures and run the script as a subprocess — never point
   them at real Claude data.
3. Keep the diff small and the code readable; prefer clarity over cleverness.
4. Make sure `ci`, `codeql`, and `security` checks pass on your PR.
5. Open a pull request describing the change and the reasoning.

First-time contributors' workflow runs may require maintainer approval before
they execute — this is intentional.

## Reporting bugs / ideas

Use the issue templates. For anything security-sensitive, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.
