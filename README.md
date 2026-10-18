# RASD | رصد — Cloud News Monitor

**Gate 28 (18 October 2026): per-article Word screenshot binding hardened.** A new offline regression proved Gate 27's unordered media hash check could accept two genuine publisher-page screenshots swapped between different articles. The final Word now requires each drawing's exact JPEG digest in the corresponding article order; swapped evidence becomes `HOLD` with no final report. See [Gate 28 acceptance](GATE28_ARTICLE_IMAGE_BINDING.md). This change does not authorize Gmail, scheduling, paid services, or multi-source production release.

**Gate 27 (17 October 2026): screenshot-to-Word evidence integrity hardening.** Final Word acceptance now verifies every embedded JPEG drawing against its independently captured publisher-page SHA-256, rejects orphan, altered, missing, and repeated picture substitutions, and removes stale same-day scratch output on HOLD. Hosted full baseline security/read-only public RSS CI passed: [Actions run 39069309452](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39069309452); 175 offline tests, one dependency-conditional skip. **This does NOT enable Gmail, private archive, source-wide production approval, or a scheduler.** See [Gate 27 acceptance](GATE27_WORD_EVIDENCE_INTEGRITY.md).

**Current product decision — 14 October 2026: WORD (.docx) ONLY.** No PDF generation, PDF attachment or PDF report artifacts in active RASD workflows. A final report is valid only when EVERY included article has an original-publisher-page screenshot embedded in its Word document and all reviewed feeds are healthy. If not, the strict report stays `HOLD` (no final DOCX). A text-only RSS Word preview remains available but is explicitly labelled **مسودة** and is NOT a final report.

**Cloud-only:** GitHub-hosted workers do not depend on the owner's laptop. APK/EXE and long-running server architecture are planned, not yet deployed. No live Gmail or automatic schedules authorized.

**Historical note:** Gate 12/13 acceptance and older lines below describing PDF document generation refer to the pre-Gate19 implementation and are superseded by the Word-only policy above. Historical evidence is kept for audit continuity.


**Status (13 October 2026): Staging / verified public-news cloud workflows; Gmail production delivery NOT enabled.**

RASD tracks **public Ministry of Planning-related headlines** from reviewed Egyptian publisher-owned RSS feeds. The public runner is hosted by GitHub Actions. All sensitive mail delivery state remains in the separate PRIVATE `Hatem1984/RASD-Pilot` repository; no user credentials or private mail receipts are committed here.

## Implemented and cloud-verified

| Capability | Status | Evidence and caveat |
| --- | --- | --- |
| Public original-source RSS | Verified | Hapi + Al Masry Al Youm. Both are real native publisher feeds; temporary outages are exposed as `DEGRADED`, not concealed. |
| Browser screenshot QA | Verified for historical **QA-only** public publisher page | [Gate 10](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38331637986). A genuinely new eligible RSS article screenshot still needs a live-match test. |
| Public observation state | Verified | Isolated public `rasd-public-state` branch, URL hashes only; three known successful runs. **Observation is not delivery.** |
| Private Gmail delivery control | Implementation and simulated E2E verified | SHA-checked private ledger, pinned recipient, at-most-one automated submission attempt, manual HOLD on uncertainty, per-run owner approval. **No real Gmail credentials or delivery yet.** |
| Private authentication-only preflight | Mock-tested | Manual protected environment required; real account access not yet configured. |
| Arabic Word + PDF | Cloud document generation and open/structure checks passed | See [Gate 12 guide](GATE12_DAILY_REPORT.md). Current genuine public RSS data, 24h Cairo report window, no invented headlines; source limitations explicit. |
| Downloadable CI report | Available | Successful report CI uploads a **1-day** public-source-only ZIP with DOCX and PDF after both files pass structural validation. |
| Unattended cron/email | **OFF** | No production schedule and no real SMTP send; both require separate acceptance and consent. |

## Current workflows

1. [Public RSS manual dry run](.github/workflows/manual-probe.yml) — original publisher feed probes only.
2. [Public state acceptance](.github/workflows/stateful-manual.yml) — public URL-hash state, manual only.
3. [Publisher screenshot QA](.github/workflows/capture-manual.yml) — public verified articles; historical fixture explicitly QA-only.
4. [Gate 11 branch CI](.github/workflows/gate11-ci.yml) — offline security regressions, live RSS read-only scan, and document-generation QA. Push-triggered on **named QA branches only**, NOT scheduled mail.
5. [Gate 11 Gmail protected bridge](.github/workflows/gate11-manual.yml) — defaults to `dry_run`; optional protected `preflight`; `send` is blocked until account-level environment secrets, fresh manual confirmation and reviewer approval exist.
6. [Arabic Word + PDF manual digest](.github/workflows/report-manual.yml) — creates DOCX/PDF and a **1-day** GitHub artifact from one RSS observation, no mail or private ledger access.
7. [Protected daily Word/PDF Gmail delivery](.github/workflows/digest-mail-manual.yml) — manual-only; code and private-ledger anti-replay fully simulated, but **no real SMTP or inbox delivery performed**. See [Gate 13](GATE13_DAILY_EMAIL.md).

## Manual Word/PDF download

1. Open [RASD Arabic daily Word and PDF](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/workflows/report-manual.yml).
2. Use **Run workflow** on `main` (requires the owner's GitHub session).
3. When the run succeeds, download the `rasd-daily-public-word-pdf` artifact under the run's **Artifacts** section. The ZIP contains one `.docx` and one `.pdf`.
4. For code-branch QA, a successful latest Gate 11 CI run publishes a separate `rasd-public-report-ci` artifact using only original public headlines. **CI packages are not proof of daily scheduled report delivery.**

An empty report means **no qualifying RSS headline was found in the sources and window checked**, not that no relevant ministry news exists on the internet. Source outages appear as `DEGRADED`. The PDF and Word use a shared observation and sort newest verified headlines **across both publishers before selecting a maximum of 15**.

## Strict security and delivery boundary

- No secrets, Gmail address, Google account password, mail tokens, signed URLs, private delivery receipts or private file content in the public repo/artifacts.
- SMTP attempt is withheld until the separate private recipient fingerprint matches and the GitHub state reservation is durably re-read.
- Real send can only be initiated by the approved owner via a **new** manual `workflow_dispatch` on `main`, a protected environment and new per-run confirmation. Re-run attempts are rejected. It is not possible to guarantee user-visible exactly-once delivery using SMTP + GitHub commits; uncertain states require manual Gmail Sent reconciliation.
- Screenshots of historic public articles are labeled testing references, never treated as fresh alerts.
- No paid browser automation, billing changes, personal Windows operations, or cron enablement were performed as part of these gates.

## Acceptance still OPEN

**Gate 11 — real protected Gmail:** The owner must configure `rasd-gmail-manual-approval` and the four eligible protected credentials in GitHub directly, then approve preflight. A later separately authorized live-mail test must prove SMTP, private acceptance receipt, Gmail Sent/Inbox image attachment, and safe re-run. Details: [Gate 11 secure setup](GATE11_SECURE_SETUP.md).

**Gate 12 — manual downloadable artifact:** cloud construction and real document QA are verified. A dedicated `report-manual.yml` GitHub `workflow_dispatch` download still requires owner initiation. Daily scheduled production and Gmail report delivery are **not** enabled.

**Gate 13 — manual daily report to Gmail:** DOCX+PDF attachment builder, private SHA state reservation, Cairo-day deduplication and per-run consent are implemented and offline-tested. Actual live protected job still awaits the same Gate 11 credential/reviewer setup and separate live-send authorization; no real message has been sent.

Use [Acceptance log](ACCEPTANCE_LOG.md) as the dated, audited source of verified results. Avoid interpreting passing unit tests as real Gmail delivery.
