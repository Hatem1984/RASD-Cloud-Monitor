# RASD | رصد — Cloud News Monitor

**Gate 30 (18 October 2026): operational README corrected to actual Word-only workflows, artifact names and live acceptance limits.** This documentation hardening changes no publishing code, Gmail configuration, secrets, private data, or scheduling.

**Gate 29 (18 October 2026): DOCX package ambiguity now fail-closed.** Duplicate ZIP part names and explicitly external screenshot image relationships are rejected even when authentic JPEG digests are present. See [Gate 29 integrity evidence](GATE29_DOCX_PACKAGE_INTEGRITY.md). No new real mail, scheduler, paid service, or production approval.

**Gate 28 (18 October 2026): per-article Word screenshot binding hardened.** A new offline regression proved Gate 27's unordered media hash check could accept two genuine publisher-page screenshots swapped between different articles. The final Word now requires each drawing's exact JPEG digest in the corresponding article order; swapped evidence becomes `HOLD` with no final report. See [Gate 28 acceptance](GATE28_ARTICLE_IMAGE_BINDING.md). This change does not authorize Gmail, scheduling, paid services, or multi-source production release.

**Gate 27 (17 October 2026): screenshot-to-Word evidence integrity hardening.** Final Word acceptance now verifies every embedded JPEG drawing against its independently captured publisher-page SHA-256, rejects orphan, altered, missing, and repeated picture substitutions, and removes stale same-day scratch output on HOLD. Hosted full baseline security/read-only public RSS CI passed: [Actions run 39069309452](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39069309452); 175 offline tests, one dependency-conditional skip. **This does NOT enable Gmail, private archive, source-wide production approval, or a scheduler.** See [Gate 27 acceptance](GATE27_WORD_EVIDENCE_INTEGRITY.md).

**Current product decision — 14 October 2026: WORD (.docx) ONLY.** No PDF generation, PDF attachment or PDF report artifacts in active RASD workflows. A final report is valid only when EVERY included article has an original-publisher-page screenshot embedded in its Word document and all reviewed feeds are healthy. If not, the strict report stays `HOLD` (no final DOCX). A text-only RSS Word preview remains available but is explicitly labelled **مسودة** and is NOT a final report.

**Cloud-only:** GitHub-hosted workers do not depend on the owner's laptop. APK/EXE and long-running server architecture are planned, not yet deployed. No live Gmail or automatic schedules authorized.

**Historical note:** Gate 12/13 previously included PDF, but that implementation is superseded; historical gate files remain available as audit records, not current operating instructions.


**Status (18 October 2026): Staging, Word-only; source-wide acceptance, protected Gmail and automatic scheduling NOT enabled.**

RASD tracks **public Ministry of Planning-related headlines** from reviewed Egyptian publisher-owned RSS feeds. The public runner is hosted by GitHub Actions. All sensitive mail delivery state remains in the separate PRIVATE `Hatem1984/RASD-Pilot` repository; no user credentials or private mail receipts are committed here.

## Current implementation and evidence

| Capability | Present status | Acceptance limit |
| --- | --- | --- |
| Native publisher RSS | Read-only cloud CI verified for Hapi and Al Masry Al Youm | Transient feed or page failures remain visible; **source health is not full-story evidence**. [18 October run](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39102185284) found both feeds healthy but zero eligible headlines. |
| Original publisher screenshot | Original Shorouk page captured in a **single-source opt-in review** | [Gate 26](RASD_GATE26_DELIVERY_ACCEPTANCE.md) does **not** approve complete production multi-source coverage. |
| Word **preview** | Arabic RSS-only `.docx`, explicitly marked **مسودة** | Downloadable public preview is **not** a final screenshot-verified report. |
| Final Word evidence | Strict original screenshot required for **every** included article | [Gate 27](GATE27_WORD_EVIDENCE_INTEGRITY.md), [Gate 28](GATE28_ARTICLE_IMAGE_BINDING.md), and [Gate 29](GATE29_DOCX_PACKAGE_INTEGRITY.md) enforce JPEG contents, per-article binding and valid DOCX package structure. Any failure → `HOLD`, no final Word. |
| Private evidence archive | Code and isolated offline simulations only | No owner-provisioned production object store, retention or restoration acceptance. |
| Private ledger/Gmail | Manual protected paths implemented and simulated | No approved hosted Gmail authentication preflight or live SMTP/inbox acceptance. |
| Automatic scheduling | **OFF** | No daily cron, automatic mail, or paid service authorized. |
| Android/Windows clients | Not deployed | Cloud API and distributable applications remain future scope. |

## Current workflows — separate preview, proof and transport

- [Main/QA read-only CI](.github/workflows/gate11-ci.yml): offline tests, real publisher feed checks and **Word-only preview**. Push on `main` and `gate*` branches; **not** a daily report scheduler.
- [RSS manual probe](.github/workflows/manual-probe.yml), [public URL-hash state](.github/workflows/stateful-manual.yml) and [capture QA](.github/workflows/capture-manual.yml): historical/development observations, not email delivery.
- [Word-only RSS preview](.github/workflows/report-manual.yml): manual `.docx` with **مسودة**; no required screenshot evidence, no private credentials, no mail.
- [Strict multi-source Word proof](.github/workflows/proof-report-manual.yml): manual original-publisher screenshot attempts; if coverage/images incomplete, `HOLD` and redacted manifest only.
- [Opt-in Shorouk strict proof](.github/workflows/gate26-strict-word-optin.yml): source-limited review, encrypted owner artifact; **not** production multi-publisher release.
- [Owner-encrypted sample QA](.github/workflows/gate25-owner-encrypted.yml) and [private proof manual QA](.github/workflows/private-proof-manual.yml): separate opt-in paths; no secret/real Gmail enablement.
- [Protected Gate11 bridge](.github/workflows/gate11-manual.yml) and [manual daily Word Gmail transport](.github/workflows/digest-mail-manual.yml): manual only, require owner-controlled GitHub environment, account credentials and separately authorized test; **not yet live-accepted**.

## Download a Word preview (NOT a final report)

1. Open [RASD Word-only preview workflow](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/workflows/report-manual.yml) and select **Run workflow** on `main`.
2. After a successful run, download the `rasd-daily-word-preview` artifact. Its ZIP includes only the `RASD-Preview-*.docx` preview, not verified article screenshots.
3. Development branch/main CI publishes a separate `rasd-word-preview-ci` artifact (also Word-only, one-day retention). A successful CI preview is **not** a final report or evidence of daily scheduled delivery.

A preview containing zero matching articles means none met the checked publisher feeds, filters and time window. It does **not** establish that no relevant news exists elsewhere. A strict final Word may be issued only after every included publisher-page screenshot has been captured, verified and linked to the correct article; otherwise it stays `HOLD`.

## Strict security and delivery boundary

- No secrets, Gmail address, Google account password, mail tokens, signed URLs, private delivery receipts or private file content in the public repo/artifacts.
- SMTP attempt is withheld until the separate private recipient fingerprint matches and the GitHub state reservation is durably re-read.
- Real send can only be initiated by the approved owner via a **new** manual `workflow_dispatch` on `main`, a protected environment and new per-run confirmation. Re-run attempts are rejected. It is not possible to guarantee user-visible exactly-once delivery using SMTP + GitHub commits; uncertain states require manual Gmail Sent reconciliation.
- Screenshots of historic public articles are labeled testing references, never treated as fresh alerts.
- No paid browser automation, billing changes, personal Windows operations, or cron enablement were performed as part of these gates.

## Acceptance still OPEN

1. **Full source coverage and genuine current-article evidence:** source-complete Word for the owner-approved production publishers, with no failed feed or screenshot; [source qualification issue #23](https://github.com/Hatem1984/RASD-Cloud-Monitor/issues/23). Shorouk remains separately opt-in.
2. **Real private evidence archive:** privately controlled storage/keys, SHA-256 read-back, retention, recovery drill, and explicit cost/security review; existing R2/S3 code is not production provisioning.
3. **Gate 11 / Gate 13 real Gmail acceptance:** [protected environment setup](GATE11_SECURE_SETUP.md), no-send authentication preflight, fresh separately approved manual send, correct private ledger receipt, Gmail Sent/Inbox reconciliation and safe replay test. No Gmail automation is authorized merely by completing code CI.
4. **Owner-approved schedule and operational monitoring:** retries, incident notification, release criteria and cost bounds; currently OFF.
5. **Full product scope if required:** authenticated API and working Android/Windows clients; currently not deployed.

Historical Gate 12/13 PDF-era descriptions are archived in [Gate 12](GATE12_DAILY_REPORT.md), [Gate 13](GATE13_DAILY_EMAIL.md) and the [dated acceptance log](ACCEPTANCE_LOG.md); they are **not** instructions for active reporting. Passing offline unit tests or source read-only scans never authorizes real Gmail sending or production release.
