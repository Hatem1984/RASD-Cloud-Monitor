# RASD | رصد — Cloud News Monitor

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

Use [Acceptance log](ACCEPTANCE_LOG.md) as the dated, audited source of verified results. Avoid interpreting passing unit tests as real Gmail delivery.
