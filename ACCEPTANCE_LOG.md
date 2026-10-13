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


## Gate 10 — real browser screenshot integrated in the public worker (13 October 2026)

- **Actual hosted runner:** [capture #1, run 38331637986](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38331637986): **SUCCESS**. Chromium + Pillow installed; **29/29 offline security/observation/image tests passed** in GitHub Actions.
- The worker read the Hapi native RSS: **10 direct publisher links**, **0 matching ministry headlines**, so **NO newly discovered headline could be photographed** in this run. It correctly used an explicitly marked **historical regression article** from El Watan (`https://www.elwatannews.com/news/details/8375816`) as the screenshot test, without adding it as a discovered story.
- Captured an original publisher page on 13 October, HTTP **200**, JPEG **1200 × 900**, **102,947 bytes**, SHA-256 `b1ba75b821df0922d42bcb45c5ff333bae53a12acaccb867f25a0fe738827ef1`.
- The result's image-quality checks passed: luminance standard deviation **68.25** and dark-pixel fraction **0.175**. The artifact JPEG and JSON were downloaded, inspected and the JPEG verified byte-for-byte against the runner's logged SHA-256; the original newspaper logo, date and exact headline are visibly rendered.
- Screenshot and report were uploaded as a **one-day public Actions artifact**, NOT committed to Git history.
- The new browser workflow retains `workflow_dispatch` only, read-only permissions, no emails, no secrets, no scheduled trigger and no state writes. Asset requests are restricted to the approved publisher domain and its subdomains.
- The two existing workflow suites were upgraded to install Pillow before running the expanded offline test discovery; they require regression cloud validation on their updated commits.
- **Acceptance:** real public publisher screenshot + visual content validation inside the RASD Cloud Monitor worker **PASS**. Automatic new-story capture is NOT confirmed until a real RSS match occurs. Gmail delivery and 30-minute cron remain OFF. No paid services were enabled.


### Gate 10 regression close — all three public worker workflows passed

Following the addition of Pillow-backed image quality tests, both older manual workflows were updated to install Python 3.11 and Pillow before running the complete suite:

- [Public RSS read-only regression run #2 — SUCCESS](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38331957801), **29/29 GitHub-hosted tests passed**; Hapi RSS returned 10 verified publisher links, zero matching ministry headlines, no mail.
- [Public stateful regression run #3 — SUCCESS](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38332020683), **29/29 GitHub-hosted tests passed**; state branch read-and-write completed. Verified `public-state.json` now has **`run_count=3`**, `last_successful_scan_utc=2026-10-13T01:25:05+00:00` and `seen_ids={}` (because no matching live ministry stories were found).
- [Public publisher browser capture run — SUCCESS](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38331637986), **29/29 tests passed**, and 1 visually accepted, real historic El Watan page screenshot in a one-day artifact.

These are **three distinct GitHub workflows** and all currently have *manual-only* triggers. The state and capture outputs are deliberately separate. No live relevant new article has been auto-captured, no email delivery has occurred from this repo and no recurring schedule is enabled.

**Gate 10 status: PASS for cloud photo QA + backward compatibility with manual public discovery and durable public fingerprint state. NOT production-ready.**


## Gate 11 — secure Gmail bridge staged, not activated (13 October 2026)

- Created a distinct private delivery branch `rasd-private-delivery-state` and empty `delivery-state.json` in existing PRIVATE `RASD-Pilot`; independently read back `entries={}`. Existing PUBLIC `rasd-public-state` remained separate and unchanged.
- Added `delivery_bridge.py`, `gate11_runner.py`, `tests/test_gate11_delivery.py`, manual default-`dry_run` workflow, and isolated CI. The Gmail send path requires an unconfigured protected environment and five separate secrets/approval fields. **No real Gmail dispatch**.
- Branch cloud security test [run 38333395107](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38333395107): **44/44 offline tests PASSED** and independent real current-feed dry-run **SUCCESS**; `eligible=0`, `captured=0`, `smtp_accepted=0`, `test_fixture_used=false`, `scheduler_enabled=false`. The zero-match behavior is verified, but no newly found relevant article has traversed the production delivery chain.
- Reviewed [PR #1](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/1), merged using squash at `041ab72d650b79c7c05166f4f802a90fd3a87fa6`. This is a **partial implementation**, not Gate 11 closure.
- No billing changes, no Windows/OneDrive writes, no passwords or approved recipient value in public code, no cron, no SMTP credentials installed, no screenshot attachments published by the new workflow.
- Still needed for Gate 11 close: verify availability of safe Google account authentication; configure GitHub protected environment and narrowly scoped private-repo write token without revealing values; obtain separate owner authorization for an actual email; prove real eligible article -> visual capture -> SMTP accepted -> private receipt persisted -> Gmail Sent/Inbox read-back -> repeat-run duplicate suppression. Avoid claiming email delivered merely on SMTP acceptance.
- Source and step-by-step safeguards: [GATE11_STATUS.md](GATE11_STATUS.md).


## Gate 11 hardening checkpoint — 13 October 2026

- [PR #2](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/2) merged at commit `5d38e2f9709076f2e7bda130586011d19386f00d`.
- Private RASD-Pilot delivery branch now has an empty schema-v2 ledger with a fingerprint of the one approved recipient. Never store the recipient value or a Gmail token in this public repository.
- The worker refuses a recipient mismatch even when SMTP sender and recipient secrets match each other; private GitHub API bearer-token redirects are rejected.
- [Hosted real cloud CI](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38335095480): **50/50 offline tests passed**, including mocked Github Contents API receipt persistence, compare-and-swap rejection, and exactly one fake SMTP attempt across repeated runs. The real feed dry-run passed with 0 qualifying articles, 0 captures, 0 SMTP, 0 fixtures and schedule off.
- No private Github credential or Gmail app password has been provisioned via this connector. The Github connector does not support deployment-environment and Actions secret APIs, so these are an explicit operational access blocker rather than a failing Python test.
- **Gate 11 remains OPEN** until a protected environment and approved account credential are provisioned, followed by genuine new-article capture, SMTP acceptance receipt, Gmail Sent/Inbox read-back and second-run no-resend proof.

