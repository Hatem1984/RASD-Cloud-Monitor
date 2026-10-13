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



## Gate 11 — private delivery read-back hardening, still no live Gmail (13 Oct 2026)

- [PR #3](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/3) merged as `49bac9f7bf54bdf1fde685b9a1d1a8528e9dc3f8`.
- The private GitHub Contents API write now requires a verifiable commit receipt and a **separate read-back** of the exact new private state plus changed blob SHA **before proceeding to SMTP**. A seemingly successful HTTP response that did not durably save a reservation no longer triggers delivery.
- Three new zero-network tests simulate a false-positive API success, an invalid commit receipt, and SMTP acceptance followed by missing receipt persistence. All reject unsafe automatic replay.
- [Hosted GitHub Actions evidence, run 38335808568](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38335808568): **53/53 offline tests PASS** plus live RSS `dry_run` PASS (0 currently eligible stories, 0 captures, 0 SMTP sends, historical-fixture flag false, schedule off).
- Read-only connector confirmation: linked Gmail is the approved mailbox; the private ledger's recipient hash equals SHA-256 of that previously authorized mailbox. Two earlier RASD subject messages were present in Sent; they are not evidence of delivery by this autonomous worker.
- The personal Windows Hatem Commander browser connection was unavailable (404), and the available GitHub connector does not expose Actions environment-secret write methods. Consequently the protected environment, account-specific Google app-password eligibility, and live SMTP delivery remain **unverified and not configured**.
- **Gate 11 remains OPEN**. No credentials pasted, SMTP test sent, automatic schedule enabled, billing change or local Windows file operation occurred in this hardening pass.


## Gate 11 — protected authentication preflight (13 October 2026)

- [PR #4](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/4) merged as `ed4cb9cced4b3f7b0cde2fddad27ddb1a7f86fa9`.
- Added `gate11_preflight.py`: separately authorized protected GitHub environment job verifies private ledger read and approved mailbox fingerprint and performs TLS Gmail SMTP **authentication only**. There are zero email transmissions and zero private ledger writes by construction. It does not grant permission for the separate `send` job.
- Added `preflight` to **manual** mode selector, protected by `rasd-gmail-manual-approval` environment; default `dry_run` and separate explicit `send` approval remain unchanged.
- Added `GATE11_SECURE_SETUP.md` with exact secure UI path, minimal private-repository token scope, four environment secret names, and explicit ban on sharing secrets in chat/public files. No secrets are configured from this connector.
- [Cloud acceptance evidence: 38336358797](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38336358797): **59/59** hosted offline tests passed; live publisher RSS `dry_run` succeeded with 0 eligible articles, 0 SMTP attempts, 0 historic fixtures and scheduling off.
- Stage **GATE11-PREFLIGHT code VERIFIED**, but **operational preflight UNRUN** (protected credentials not available). Gate 11 **OPEN** pending privileged GitHub environment configuration, real authentication-only protected job, explicit consent for actual cloud send, SMTP/private receipt, Gmail Sent/Inbox readback and no-replay evidence.


## Gate 11 coverage checkpoint — two publisher-owned live RSS sources (13 October 2026)

- [PR #5](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/5) merged as `703e0992a0204871e5c8902fa74738f121eade02`.
- Verified original publishers: existing Hapi RSS and the additional independently checked [Al Masry Al Youm native RSS](https://www.almasryalyoum.com/rss/rssfeeds). **Both feeds are used in dry-run only**; do not interpret an article fixture as a new discovery.
- RSS fetch is now pinned to **exactly two reviewed URLs** instead of opening all paths on a trusted domain. Native article-domain capture is separately constrained to the original publisher. No Google News proxy or aggregator URL can be emailed as an original publisher.
- Safe observability was added to gate11_runner result: healthy/failed original-feed counts, verified publisher article link count, and exact planning headline match count. No user address, access token, article body, or private state is included.
- [Hosted GitHub Actions run 38336995776](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38336995776): **65/65 offline tests PASSED**, public live-feed dry-run **SUCCESS**, `healthy_sources=2`, `failed_sources=0`, `verified_publisher_links=60`, `planning_headline_matches=0`, `eligible=0`, `smtp_accepted=0`, `scheduler_enabled=false`.
- These are verified source-access/QA improvements, **not** proof of genuine news capture/send to Gmail. Protected Github Actions environment/secrets and actual preflight remain pending; live cloud Gmail delivery and inbox/attachment readback remain unproven. **Gate 11 remains OPEN.**

## Gate 11 operations hardening — fresh human consent and feed-health transparency (2026-10-13)

- [PR #6](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/6) squash-merged at `ff8e2def7e3ee675fe24125b6264868d7918c0a5`.
- Protected Gmail `send` now requires, in addition to the environment secret and separate GitHub environment reviewer configuration, a new human-typed `send_confirmation` on each `workflow_dispatch`. The runner requires `main`, the exact existing public repository, initiating actor `Hatem1984`, a numeric new GitHub run ID and run attempt 1. Any GitHub Actions rerun attempt fails closed. No schedule was configured.
- An intermittent partial source failure was **actually observed** in [CI run 38337893388](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38337893388): `healthy_sources=1`, `failed_sources=1`. Treat this as degraded coverage, not proof that both feeds were healthy at all times. A transient publisher refusal can cause this without changing worker code.
- Added structured **public-only** `source_health` feed IDs, `coverage_status` and safe failure class labels to the no-mail live scan, with a GitHub Actions warning for partial coverage; no secret, recipient or article content in logs. A single healthy feed can still be processed, but partial coverage is explicitly **DEGRADED** and requires investigation.
- Latest fully integrated [hosted CI 38338078066](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38338078066): **72/72 offline tests passed** and real-world publisher check returned `coverage_status=healthy`, `healthy_sources=2`, `failed_sources=0`, `verified_publisher_links=60`, `planning_headline_matches=0`, `smtp_accepted=0`, no fixture, no scheduler.
- The protected environment/secrets remain unconfigured by ChatGPT; no true Gmail authentication or SMTP/Inbox verification was performed. **Gate 11 remains OPEN.**


## Gate 11 full pipeline acceptance — 13 October 2026

- [PR #7](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/7) squash-merged as `71f22180df4502a2ab3c6ce0164fb008af54dcf5`.
- Added seven independent, no-network **integration regression tests** covering the actual `gate11_runner.run("send")` orchestration: two separate reviewed RSS feeds -> publisher-title and screenshot checks -> actual `deliver_reserved` code -> mocked GitHub private branch compare-and-swap/readback -> mocked SMTP acceptance -> repeat workflow simulation with no automatic second send.
- Also verified historical RSS is excluded, wrong article-page title blocks any reservation, partial publisher outage retains valid healthy-feed processing while reporting DEGRADED, unauthorized actor cannot access the feed in send mode, and a lost private SMTP receipt after accepted fake SMTP leaves the article in manual HOLD rather than automatic resend.
- **Testing boundary:** all article dates, captures, private GitHub API responses, credentials, and SMTP transmissions in the seven E2E tests are simulated; these tests do **not** prove genuine Gmail delivery.
- [Cloud execution 38341343890](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38341343890): **79/79 offline tests PASS**; separate **actual** publisher RSS dry-run reports `healthy_sources=2`, `failed_sources=0`, `verified_publisher_links=60`, `planning_headline_matches=0`, `smtp_accepted=0`, `scheduler_enabled=false`, with no historic fixtures.
- Gate 11 remains **OPEN** pending protected GitHub environment setup, real authentication-only preflight, explicitly approved genuine new-article SMTP submission, private receipt verification, Gmail Sent/Inbox attachment verification, and one more no-replay proof. No scheduling, billing change, new account secrets or local Windows file changes.


## Gate 12 — Arabic daily Word and PDF files from public native RSS (13 October 2026)

- [PR #8](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/8) merged at `870d302c071fc12079b76c6534767d9b3a5e9f1f`. Real source-backed Word and PDF report generation is implemented in `daily_report.py`, with guidance in `GATE12_DAILY_REPORT.md`.
- Report scans the two reviewed native RSS publishers **once per report**, constrains articles to 24 hours, reuses existing publisher/date/provenance checks, labels Cairo time, and creates Arabic RTL DOCX and printable PDF from the exact same observation. PDF news links remain clickable and HTML-escaped. No data outside the reviewed publisher list is added.
- No matches produces an explicit zero-story report. Partial source outage is shown as `DEGRADED`; all-source outage fails closed without generating a misleading empty report. Report carries explicit limited-coverage warning (RSS titles, max 15 matching items).
- New **manual-only** `.github/workflows/report-manual.yml` generates both formats and publishes one **public-headlines-only** ZIP artifact for 1-day download; no Gmail, cron, passwords or private ledger calls. Artifact download requires an **actual new manual dispatch**, which the current GitHub connector cannot perform.
- [Latest hosted CI 38342570177](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38342570177): **87/87 tests PASS** and genuine cloud Word+PDF creation/structural validation PASS. Source data was partially available this run: `sources_healthy=1`, `sources_failed=1`, `coverage=DEGRADED`; `articles=0`, `email_sent=false`, `scheduler_enabled=false`.
- **Gate 12 file-generation code ACCEPTED.** Live manually downloadable artifact has not yet been dispatched. Automatic daily mail attachments and the separately blocked protected Gmail Gate 11 remain **OPEN**; no live SMTP or inbox check has been completed.


## Gate 12 operational deliverable — real downloadable Word/PDF and cross-source reliability (13 October 2026)

- [PR #9](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/9) merged as `cbac4af505647ef0ec6a0a5fc3fce12f880f7c4e`.
- Previously, Gate 12 DOCX/PDF were validated on the cloud worker but not attached to a runnable branch CI run; CI now publishes a downloadable **public headlines-only** artifact named `rasd-public-report-ci` after passing both-document checks, with retention only **one day**. This does **not** enable daily cron or Gmail email.
- Corrected an actual report accuracy risk: the compact public monitor capped matches at 15 before sorting, potentially hiding the newest article from the second source. The report now scans a bounded 200 validated candidates across both sources, sorts by real publisher timestamp, then selects 15 newest, while the original public monitor still defaults to 15.
- Corrected mixed Arabic/ISO+EEST date display to readable Arabic Cairo day/month/time, preserving ISO filename metadata. Verified resulting PDF and DOCX **visually** after downloading the genuine GitHub Actions ZIP, not only by structural checks.
- Added one bounded retry for upstream RSS XML parse corruption, connection timeout, or specific transient HTTP errors, while preserving strict exact source allowlist, no redirects, no unsafe XML, and hard failure when both publishers are down.
- [Final hosted CI 38343863331](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38343863331): **91/91 offline regressions PASS**, genuine cloud original-source scan `healthy_sources=2`, `failed_sources=0`, `verified_publisher_links=60`, `planning_headline_matches=0`; generated PDF and Word both opened and verified, artifact `11788610140` / `rasd-public-report-ci` downloaded and independently visually inspected. Report snapshot reflects **zero matching headlines**, not proof no ministry news existed on other sites.
- Private mail ledger and public observation state were not modified by this release. GitHub's `rasd-gmail-manual-approval` protected environment/secrets and live authentication have **not been configured**, so **Gate 11 Gmail production is OPEN**, SMTP delivery remains zero and no cron/scheduler is active.


## Gate 13 — protected daily Word/PDF Gmail transport implementation (13 October 2026)

- [PR #10](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/10) merged at `92fe51690365347ed81f2ce5e1976abe091bcfa8`.
- Added `digest_mailer.py`, a **separate manual-only** owner-approved workflow `.github/workflows/digest-mail-manual.yml`, [Gate 13 operational guide](GATE13_DAILY_EMAIL.md), and nine true orchestration regressions with *fake* Gmail SMTP and *fake* GitHub private ledger.
- Manual daily digest generates the real Word and PDF from original public native RSS only, validates both with python-docx and pypdf **before** private reservation, attaches them to one self-addressed Gmail message, and stores a unique hashed key per **Cairo calendar day** in the existing private SHA/CAS ledger. A second attempt for the day returns `already_accepted` or `manual_review_hold`, not a second SMTP submission.
- Send requires same existing protected GitHub environment/secrets, owner actor, manually dispatched `main` run attempt 1, exact dedicated workflow reference, and a fresh operator typed confirmation. On unexpected SMTP outcome or durable receipt failure, manual review is required; no cron or automatic retry was activated.
- [Final hosted CI 38344950939](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38344950939): **100/100 offline tests PASSED**. Real original RSS read-only dry-run: `healthy_sources=1` and `failed_sources=1` (intermittent Al Masry Al Youm ParseError), `verified_publisher_links=10`, `planning_headline_matches=0`; real PDF and DOCX creation and ZIP artifact verification succeeded with `coverage=DEGRADED`, `articles=0`. No real SMTP attempted in CI.
- **Gate 13 code VERIFIED / actual delivery OPEN.** The connector cannot provision GitHub Environment Secrets or validate actual Gmail App Password. Protected preflight, first genuinely authorized live SMTP attempt, Sent/Inbox attachment readback and second-run no-replay require owner-controlled GitHub setup and explicit permission. This is NOT production-ready automated delivery.


## Gate 14 — manual workflow dependency repair and safe main CI (13 October 2026)

- [PR #11](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/11) merged at `04de036625e90a2c1b332b566f3517e94049816a`.
- Verified a real deployment blocker: the existing manual `preflight`, `capture`, `stateful`, `manual-probe`, and Gate 11 `dry_run/send` jobs ran the full offline test suite but installed only Pillow (and sometimes Playwright). Since Gate 12/13 the suite also imports `python-docx` and `pypdf`, so old jobs would fail **before** their actual RSS, state or Gmail checks.
- Centralized `Pillow`, `python-docx`, and `pypdf` into `requirements-test.txt`. Updated **all seven** existing Actions workflows to install that same manifest and retain Chromium/Playwright only where needed. Added five pure offline workflow-dependency and no-cron contract tests.
- Enabled **read-only on-push main CI** to catch future regressions. This is development QA (no credentials, no SMTP, no cron, no private state writes), NOT automatic news publishing or mail dispatch.
- [Final tested branch run 38391853536](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38391853536): **105/105 offline tests PASS**; original RSS fetch **HEALTHY 2/2**, `verified_publisher_links=60`, `planning_headline_matches=0`; cloud Word+PDF structural validation and artifact publication PASS.
- No protected environment or Gmail App Password was provisioned, and no preflight or real Gmail SMTP job has run as a result of this patch. **Gate 11 and real Gate 13 delivery remain OPEN** pending owner-managed GitHub protected credentials and genuine authentication/delivery acceptance.


## Gate 15 — private ledger first, fail-safe same-day digest replay (2026-10-13)

- [PR #12](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/12) squash-merged at `95713188f4b918a8c3747fad83669f5a0bc6a825`.
- The previously verified manual digest pipeline scanned original publisher RSS and regenerated Word/PDF before discovering an existing same-day `smtp_accepted` or reserved/HOLD receipt. This was unnecessary, could waste free runner minutes, and could make a safe duplicate-check fail merely because a publisher was temporarily unavailable.
- New flow: verify fresh owner/manual execution authorization and exact approved private-recipient hash, **read the existing PRIVATE ledger first**, and if the Cairo-day key already exists return `already_accepted` or `manual_review_hold` with `source_scan_skipped=true`, `articles=null`, and `coverage=NOT_RESCANNED`. It does NOT claim newly checked source health and does not regenerate documents or attempt SMTP.
- A first-time report still obtains and renders current publisher RSS/Word/PDF and uses the existing atomic SHA compare-and-swap reservation with readback BEFORE any SMTP. This read-only early check does not substitute for durable first-time reservation.
- [Live cloud CI 38397354974](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38397354974): **107/107 offline tests PASS** including same-day reply after total source failure, HOLD short-circuit, and wrong pinned recipient rejection before RSS; actual public sources HEALTHY 2/2, 30 inspected publisher links, zero matched original news, PDF/DOCX generated and verified, SMTP 0, no scheduler.
- GitHub environment settings/secrets cannot be configured through the connected GitHub integration. The same protected environment and manual approval remain mandatory for real Gmail preflight/send. **Real Gmail SMTP and inbox delivery remain UNVERIFIED.**
