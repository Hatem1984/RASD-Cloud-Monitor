# Initial cloud acceptance record — 13 October 2026

## Repository creation

- Repository: [Hatem1984/RASD-Cloud-Monitor](https://github.com/Hatem1984/RASD-Cloud-Monitor)
- Repository visibility: **PUBLIC**, verified using GitHub repository metadata.
- The original private RASD platform was **not copied** here. No SMTP tokens, credentials, recipient addresses, private articles or private project files were committed.

## Real GitHub Actions test

- Run [#1 — ID 38329569019](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38329569019)
- Status: **COMPLETED / SUCCESS**
- Offline test suite: **10 tests / 10 passed**, as reported in the runner log.
- Public Hapi RSS fetch: **SUCCEEDED**.
- Publisher-owned HTTPS article links parsed: **10**.
- Planning ministry headline matches during this single sample: **0**.
- Evidence artifact: [rasd-public-news-manual-probe](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38329569019/artifacts/11781744911), retained for one day.
- Email sent: **NO**; no Gmail functionality has been installed in the public worker.
- Cron / schedule: **OFF**; only manual `workflow_dispatch` exists.
- Persistent cross-run deduplication: **NOT IMPLEMENTED**; current URL hashing only deduplicates within one run.

## Follow-up acceptance items (not yet done)

1. Private-safe persistent delivery/seen-state design and actual across-run idempotency tests.
2. More verified direct publisher sources: tested Youm7 feed returned malformed XML and is **not** activated.
3. Public-article screenshot capture with visual-content rejection, reusing concepts proven in the separate public proof but not copying private RASD code.
4. A secure Gmail delivery bridge, without publishing credentials or recipient addresses.
5. Only after the above gates and confirmed $0 spending controls: separately authorize and activate 30-minute scheduled runs.

The current test is a **working cloud dry-run**, not an autonomous production news monitoring service.


## Gate 9 — durable public URL observations, two real cloud runs

- Added `public_state.py` + `stateful_probe.py`, a separate `stateful-manual.yml` workflow and `tests/test_public_state.py`. No production cron or Gmail steps.
- Tests executed in the GitHub-hosted runner: **19 of 19 passed** in the second run, including two-run fingerprint dedupe with an offline relevant-article fixture, retention, invalid-file fail-closed, and no email side effects.
- [Stateful run #1](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38330223809): **SUCCESS**. Created the separate `rasd-public-state` branch and its `public-state.json` with `run_count=1`.
- [Stateful run #2](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38330365566): **SUCCESS**. Loaded existing `public-state.json`, completed a new RSS read, then committed `run_count=2`, independently read back from GitHub at `2026-10-13T01:04:34+00:00`.
- **Real RSS matching stories:** zero in both of these live runs. The `seen_ids` map therefore remains empty. This proves real cross-run state continuity, NOT live duplicate suppression of a repeated relevant article. That behavior passed only the synthetic no-network fixture test.
- State stores only hashed public source URLs, first observation timestamps and scan counters; it has no messages, credentials, names, recipient addresses, email status or private project files.
- Important distinction: these are **observations**, not delivery receipts, and GitHub Actions `contents: write` permission is repository-wide even though the workflow pushes exclusively to the public state branch.
- **Acceptance:** GitHub runner and branch persistence PASS. Automated daily monitoring / screenshot-in-worker / private Gmail delivery / exactly-once email remain NOT implemented or enabled.
