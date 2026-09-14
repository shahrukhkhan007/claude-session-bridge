# Security Policy

## Scope and design

`claude-session-bridge` runs entirely on your machine. By design it:

- makes **no network calls** of any kind;
- never reads, stores, or transmits **credentials or authentication tokens**;
- only **reads** conversation transcripts (`~/.claude/projects/`) — never writes
  or deletes them;
- only **adds or moves** small sidebar-registration JSON files, and takes a
  backup of the index folder before any change.

Because it touches the Claude desktop app's internal, undocumented storage,
treat every release as best-effort and always run the default dry run first.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Instead, use **GitHub's private vulnerability reporting**:
open the repository's **Security → Report a vulnerability** tab
(<https://github.com/shahrukhkhan007/claude-session-bridge/security/advisories/new>).

Include: what you found, how to reproduce it, and the impact you expect. You'll
get an acknowledgement within a few days. Please give a reasonable window for a
fix before any public disclosure.

## For contributors and reviewers

Pull requests run against automated checks (tests, CodeQL, Bandit, Ruff,
Gitleaks). CI uses the `pull_request` trigger, so code from forks runs **without
access to repository secrets**. Reviewers should still read every change to the
file-writing paths carefully, since this tool manipulates the user's local app
data. In particular, reject any change that:

- adds a network call, telemetry, or any outbound request;
- reads credential files, keychains, or environment secrets;
- deletes or overwrites transcript files, or removes the backup step;
- shells out to external commands.
