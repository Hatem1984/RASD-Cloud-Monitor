# RASD Cloud Monitor — Public News Worker (staging)

A standalone monitoring worker for **publicly published** Egyptian Ministry of Planning news. This public repository remains separate from the private `RASD-Pilot` code and the earlier public browser-proof repo.

## Status: verified cloud acceptance, NOT autonomous production

- **Public RSS inspection:** tested on real GitHub-hosted runner.
- **Durable public URL observation state:** tested successfully in **two separate GitHub Actions runs**.
- **Full integrated offline regression suite:** **29/29 PASS** on the real GitHub-hosted browser-capture run.
- **Scheduling:** OFF. All three workflows are `workflow_dispatch` only.
- **Gmail delivery:** OFF. No Gmail keys, addresses, attachments, recipient lists or private user records are stored in this repository.
- **Publisher screenshots:** INTEGRATED AND CLOUD-TESTED via independent, manual, public-source-only Chromium workflow with image-quality checks. **Word/PDF and Gmail delivery:** not integrated in this worker; automated end-to-end delivery is not proven.

## Source coverage and truthful status

The only currently validated direct-feed source here is `https://hapijournal.com/feed/`. The latest live probes read 10 direct publisher URLs but found zero matching Ministry of Planning headlines. Zero results **do not prove** that no relevant news exists or that the system has comprehensive publisher coverage. The Youm7 RSS endpoint previously failed standard XML parsing in a separate cloud trial and remains disabled.

## Three deliberately separate manual workflows

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

## 3. Manual, source-verified screenshot workflow

**Actions → RASD publisher capture — manual only, no email.** This workflow installs Chromium and Pillow on the free hosted runner, runs all 29 offline tests, reads the reviewed Hapi feed, and photographs at most two matching original publisher pages. It rejects unrelated domains, redirects outside reviewed publisher hosts, blank screenshots, non-news pages, and unusual network URLs. The public screenshots and audit JSON are kept as GitHub Actions artifacts for **one day**, not committed to Git history.

When RSS contains **zero matching headlines**, it photographs a separately labeled **historical El Watan public article dated 12 October 2026**, ONLY to verify that real browser screenshots still work. This image must **never** be presented as a newly discovered relevant item or trigger a news alert. Visual inspection and the QA gate both passed in the first cloud test.

- [Gate 10 real cloud screenshot run — success](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38331637986)
- [GitHub short-lived screenshot and JSON artifact](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38331637986)
- Live test: Hapi 10 direct RSS links, 0 matched; historical El Watan screenshot 102,947 bytes, HTTP 200, visual standard deviation 68.25, dark pixel fraction 0.175, accepted and manually viewed.

## Evidence

- [Cloud state run #1 — success](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38330223809)
- [Cloud state run #2 — success](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38330365566)
- [View persisted public state](https://github.com/Hatem1984/RASD-Cloud-Monitor/blob/rasd-public-state/public-state.json)
- Offline fixture tests prove the same relevant URL is observed **once across two simulated runs**; live RSS happened to return zero matching headlines, so a real-world repeated relevant URL has not yet been observed twice.

## Next acceptance gates

1. Expand tested direct publisher coverage without accepting malformed RSS or Google News links as original publisher URLs.
2. **Completed for known reference:** capture and visually validate a real publisher webpage in this worker; **pending**: independently capture a genuinely new RSS-discovered ministry article when a match appears.
3. Separate private delivery from public discovery. **Observed does not mean sent**. Prove secure, idempotent Gmail dispatch without publishing tokens or private delivery state.
4. Authorize and test automatic 30-minute scheduling only **after** delivery, usage controls, and other risks are settled.

No new spending, GitHub billing changes, operations on the user's PC filesystem, email dispatch or automatic schedule was performed for these manual acceptance gates.
