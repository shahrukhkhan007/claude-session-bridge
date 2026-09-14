# Protecting `main`

GitHub branch protection is configured in the repo's web UI (it can't live in a
committed file). Do this once after the first push, when the CI workflows have
run at least once so their check names appear.

## Steps

1. Push the repo and open a throwaway PR (or push once to `main`) so the **CI**,
   **CodeQL**, and **Security** workflows run and register their check names.
2. Go to **Settings → Branches → Add branch ruleset** (or "Add rule" under
   *Branch protection rules*) and target `main`.
3. Enable:
   - **Require a pull request before merging**
     - Require at least **1 approval**
     - **Dismiss stale approvals** when new commits are pushed
     - **Require review of the most recent push**
   - **Require status checks to pass before merging**
     - Require branches to be **up to date** before merging
     - Select these checks:
       - `tests (py3.9)` … `tests (py3.13)` (both `ubuntu-latest` and `macos-latest`)
       - `analyze (python)` (CodeQL)
       - `bandit (python security)`
       - `ruff (lint)`
       - `gitleaks (secret scan)`
   - **Require conversation resolution before merging**
   - **Require signed commits** (recommended)
   - **Do not allow bypassing the above** (applies rules to admins too)
   - Optionally **Require linear history**
4. Save.

## For public contributions

- Under **Settings → Actions → General → Fork pull request workflows**, set
  first-time (or all outside) contributors to **require approval to run
  workflows**. This stops untrusted PR code from running automatically.
- The workflows already use the `pull_request` trigger (not
  `pull_request_target`) and `permissions: contents: read`, so forked-PR runs
  have **no access to secrets** and cannot push to the repo.
- Keep the **Security** and **CodeQL** checks in the required list so no PR can
  merge without passing them.
