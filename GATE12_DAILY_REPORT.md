# RASD Gate 12 — Arabic Daily Word & PDF (public source report)

## Current scope — verified separately from Gmail Gate 11
- Single **manual** GitHub Actions job: `.github/workflows/report-manual.yml`.
- Reads current publisher-owned RSS feeds from the two reviewed endpoints in `sources.json`; validates article publisher, date and headline with the existing RASD checks; selects articles published in the **last 24 hours** and labels the report window in Cairo local time.
- Writes **DOCX + PDF from the SAME source observation**, including publisher link and publication time. Empty result explicitly says there were no matching stories; no fabricated news, no historical fixtures in this workflow.
- Clearly records each feed's availability. If one publisher fails, report has `DEGRADED` status. If all feeds fail, no report is produced.
- Never sends email, reads Gmail secrets, writes private RASD state, schedules itself, or contacts news aggregators.
- Only public-source headlines and links are included in short-retention public GitHub Actions artifacts. Review account storage/billing rules before increasing retention or scheduling.

## Download a report manually
1. Go to [GitHub Actions](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions).
2. Open **RASD Arabic daily Word and PDF — manual public sources only**.
3. Click **Run workflow** on `main`. The worker downloads the latest genuine public RSS feeds and renders the two files.
4. Open the successful run; under **Artifacts** download `rasd-daily-public-word-pdf`. This zip contains the original `.docx` and `.pdf` reports and is retained for **1 day**.
5. Do not treat a zero-story report as proof no ministry news existed elsewhere. This is headline-only monitoring of the currently approved source list.

## Safety and acceptance
- CI first validates all unit tests, generates actual DOCX/PDF from current original RSS, and opens both files structurally. A future manual run also validates these before presenting the artifact.
- Gate 12 Word/PDF file-generation infrastructure is a separate milestone. **Daily scheduled production** and **Gmail automatic report delivery are not enabled** and require a separate approved scope and account credentials, plus actual inbox acceptance tests.
- The current PDF uses Playwright Chromium with embedded HTML but blocks **all resource requests** from the PDF page to prevent network data exfiltration.
- No personal sender address, credentials, private delivery ledger, screenshot fixture or content from outside approved publishers may enter this artifact.
