# RASD Cloud Monitor — Public News Worker (staging)

A standalone monitoring worker for **publicly published** Egyptian Ministry of Planning news. This public repository remains separate from the private `RASD-Pilot` code and the earlier public browser-proof repo.

## Status: verified cloud acceptance, NOT autonomous production

- **Public RSS inspection:** tested on real GitHub-hosted runner.
- **Durable public URL observation state:** tested successfully in **two separate GitHub Actions runs**.
- **Security + state regression suite:** **19/19 PASS** on GitHub.
- **Scheduling:** OFF. Both workflows are `workflow_dispatch` only.
- **Gmail delivery:** OFF. No Gmail keys, addresses, attachments, recipient lists or private user records are stored in this repository.
- **Screenshots and Word/PDF:** NOT integrated in this worker. These features were separately tested, but automated end-to-end delivery is not proven.

## Source coverage and truthful status

The only currently validated direct-feed source here is `https://hapijournal.com/feed/`. The latest live probes read 10 direct publisher URLs but found zero matching Ministry of Planning headlines. Zero results **do not prove** that no relevant news exists or that the system has comprehensive publisher coverage. The Youm7 RSS endpoint previously failed standard XML parsing in a separate cloud trial and remains disabled.

## Two deliberately separate manual workflows

**1. RASD public monitoring — manual dry-run only**

Read-only permissions (`contents: read`), offline tests, one public RSS read, short-lived count artifact. No state mutation.

**2. RASD state persistence — manual acceptance only**

Runs the same public intake and offline tests, then reads the existing isolated branch `rasd-public-state`, merges newly observed public article URL *hashes*, and writes back `public-state.json`.

- Stores **only** schema version, count of successful runs, latest successful scan timestamp, and public URL identity hashes with timestamps.
- Does **not** store article texts, screenshots, mailboxes, recipients, delivery status or passwords.
- The branch is **PUBLIC**, as are any data committed there. Never use it for private news, emails, delivery receipts or sensitive fields.
- The stateful workflow uses repository-scoped `contents: write` permission to push its state branch. This token is *not technically restricted* to that branch by GitHub permissions; the job itself is coded to write only that branch.
- Concurrent stateful workflow runs are serialized by a shared Actions concurrency group.
- A broken/missing expected state file fails closed; source outages cannot silently erase the previous state.
- If no matching story appears, the run counter still advances. This proves continuity, not a successful detection.

## Evidence

- [Cloud state run #1 — success](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38330223809)
- [Cloud state run #2 — success](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38330365566)
- [View persisted public state](https://github.com/Hatem1984/RASD-Cloud-Monitor/blob/rasd-public-state/public-state.json)
- Offline fixture tests prove the same relevant URL is observed **once across two simulated runs**; live RSS happened to return zero matching headlines, so a real-world repeated relevant URL has not yet been observed twice.

## Next acceptance gates

1. Expand tested direct publisher coverage without accepting malformed RSS or Google News links as original publisher URLs.
2. Capture and visually validate real webpage screenshots in this worker, based on independently verified public test techniques.
3. Separate private delivery from public discovery. **Observed does not mean sent**. Prove secure, idempotent Gmail dispatch without publishing tokens or private delivery state.
4. Authorize and test automatic 30-minute scheduling only **after** delivery, usage controls, and other risks are settled.

No new spending, GitHub billing changes, persistent operations on the user's PC, email dispatch, or automatic schedule was performed for this state acceptance gate.
