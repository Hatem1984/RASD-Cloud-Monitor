# RASD Gate 11 — one-time secure Gmail environment setup (not yet provisioned)

**Status:** No secrets, Gmail app password or fine-grained private-ledger token have been created by this repository work. The public GitHub code is NOT production-enabled; scheduling is OFF. Follow only after explicitly reviewing the permission and cost boundary.

## Why one authorized GitHub UI step remains

The existing GitHub ChatGPT connector can safely edit code and run CI, but does **not** expose GitHub repository **Settings > Environments > Secrets** or Google account security management. The assistant cannot create account credentials or approve a protected deployment through this connection. **Never paste passwords, app passwords, PATs, OTPs or recovery codes into chat, code, commits, issue text or public logs.**

## Configure on GitHub directly, without local PC files

1. Open **https://github.com/Hatem1984/RASD-Cloud-Monitor/settings/environments** while signed in as repository owner.
2. Create environment named exactly `rasd-gmail-manual-approval` (or edit it if it already exists). Set **Required reviewers** to an authorized human, disable admin bypass if the UI offers it, and restrict **Deployment branches** to `main`. If the only intended reviewer is also the operator who dispatches the job, do not enable `Prevent self-review` without an independent reviewer; otherwise no authorized review can succeed.
3. Ensure `main` changes are reviewed before allowing any protected job; restrict untrusted write collaborators. Repository is PUBLIC **only for code and read-only sources**, not data or secrets.
4. In **environment secrets** (NOT repository-level plaintext variables), create four names, with values entered **directly in GitHub UI**:
   - `RASD_GMAIL_USER`: the pre-agreed Gmail sender.
   - `RASD_APPROVED_RECIPIENT`: exactly the same pre-agreed recipient.
   - `RASD_GMAIL_APP_PASSWORD`: a newly generated **app-specific** Gmail password, only if the account is eligible and its owner deliberately approves. Never use the regular Google password. If unavailable, STOP and choose a separate future OAuth solution.
   - `RASD_PRIVATE_LEDGER_TOKEN`: a fine-grained PAT created in the account with access exclusively to `Hatem1984/RASD-Pilot`, **Contents read/write**. Never give it access to all repositories. Use the shortest practical expiry; renew safely before expiration.
5. **Do NOT set** `RASD_GATE11_SEND_APPROVED` yet. This fifth secret is the independent live-send authorization and must remain absent pending a separately reviewed real-mail test.

## Two separate operational checkpoints

**A. Protected preflight only (no email):**
- In **Actions > RASD Gate 11 — secure Gmail bridge > Run workflow**, select branch `main`, mode **`preflight`**, then approve the protected environment. The result shows only booleans/counters.
- This reads the private ledger and its approved-recipient fingerprint and performs a Gmail SMTP TLS **login only**. It never calls `send_message` or `sendmail`, never alters private ledger data, and has no scheduler.
- A valid preflight does **not** prove mail delivery. Google may log a security login event. A failed preflight stops safely.

**B. Live send, later and only with separate authorization:**
- First review one genuinely NEW dated article on an approved original publisher. Historical samples are forbidden.
- After explicit operator approval, add the fifth environment secret `RASD_GATE11_SEND_APPROVED` with exact project-approved phrase (see trusted `gate11_runner.py`; don't paste in chat).
- Manually select `send`, approve the environment, check private reservation and `smtp_accepted` receipt, then verify Gmail Sent/Inbox and the original screenshot attachment from the connected Gmail account. Run a second manual test to show non-resend.
- Keep all `schedule:` triggers OFF until the entire Gate is accepted.

## Risk and cost boundary

Public GitHub-hosted standard Actions runners and public repository environments are available at zero additional cost under GitHub's current policy, **subject to the account's settings and normal platform policies**. Never change billing or activate an optional metered web/browser service for this procedure. Gmail App Passwords require Google 2-Step Verification and are not available for some account configurations. No action in this guide proves eligibility on this particular account.

Official docs:
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
- https://support.google.com/accounts/answer/185833?hl=en


## Gate 11 operator consent hardened (13 October 2026)

The `send` mode now needs **both** the existing protected fifth secret and a **new confirmation text typed on every fresh GitHub workflow dispatch** in the `send_confirmation` input. For preflight/dry-run leave that input empty. The safe value is documented in the reviewed public `gate11_runner.py`; it is an explicit human acknowledgment, **not** a password or replacement for the environment required reviewer.

The production sending function fails closed unless all of these GitHub-provided facts match: event `workflow_dispatch`, branch `main`, repository `Hatem1984/RASD-Cloud-Monitor`, initiating actor `Hatem1984`, a numeric GitHub run ID and **run attempt exactly 1**. Using GitHub **Re-run jobs** on a previously approved send can never authorize another SMTP attempt; dispatch a new manually approved workflow instead. These checks do not configure a reviewer automatically; repository owner must still configure the protected environment, reviewers and secrets via GitHub Settings before any real preflight.

No permanent schedule, credential, website automation subscription or paid action was created by this change.
