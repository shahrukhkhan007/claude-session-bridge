## What this changes

Briefly describe the change and why.

Fixes #<!-- issue number, if any -->

## Checklist

- [ ] I added/updated tests in `tests/test_bridge.py` and they pass
      (`python3 -m unittest discover -s tests -v`)
- [ ] `ruff check .` and `bandit -r claude_session_bridge.py --severity-level medium` pass
- [ ] No new network calls, no credential access, no third-party runtime deps
- [ ] Transcripts remain read-only; a backup is still taken before any write
- [ ] README/docs updated if behavior or flags changed

## Notes for reviewers

Anything to look at closely (especially file-writing paths).
