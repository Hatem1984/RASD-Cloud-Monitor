# Gate 23 — exact Cairo-day, 20-item PUBLIC pilot preview

Date: 15 October 2026. Scope: report quality and safe display ONLY; no private credentials, cloud storage, Gmail, billing, scheduling, or producer-rights changes.

## Why

The operator asked to review up to 20 articles from 08:00 Cairo to the time of a live run. Earlier RASD previews used a rolling 24-hour window and a 15-item cap; these are different requests. Gate 23 adds *optional* exact-window controls while preserving existing production/strict-proof defaults.

## Explicit semantics

- The allowed custom window must begin **today in Cairo**, be within 24 hours of the as-of time, and must not start in the future. All timestamps are timezone-aware.
- Accept only validated items from the two existing allowlisted publisher-owned RSS feeds; article publication time must be inside the exact inclusive window. Process candidates across both feeds *before* sorting newest first and applying cap.
- At most 20 articles can appear in the **public preview**; production proof/report delivery retains the earlier 15-article default, unchanged.
- Duplicate article URLs are counted only once. **This is NOT event-level deduplication.** Multiple articles from different publishers about the same event are not silently collapsed. Independently reviewed event counts remain unknown until assessed by an editor.
- A feed failure is marked `DEGRADED`, not treated as full coverage; all-source failure stops. 20 is an upper limit, not an invented quota.
- The Word document labels itself **مسودة** and says no verified original-publisher page screenshots are included. A publisher image/thumbnail is NEVER an authenticated browser screenshot. Screenshot-final report rules remain separate and fail-closed.
- No source analysis facts, sentiment, promises, ratios or executive conclusions are generated without articles actually being read and editorially verified. Counts and source distribution are factual mechanical diagnostics, not political or financial analysis.
- No private ledger, email or cron is touched.

## Run

From the existing repository on a day after 08:00 Africa/Cairo:

```bash
python daily_report.py --output-dir report-output \
  --start-cairo 2026-10-15T08:00 --max-articles 20
```

The example day is **historical after that date**. For a fresh run, substitute the actual Cairo date. CLI returns a structured summary including exact window, counts, truncation, `events_verified: null`, and `publisher_screenshots_verified: 0`.

The read-only GitHub branch CI now automatically exercises the same *relative* 08:00 Cairo pilot after 08:00 local time; earlier hours retain the old rolling-window check. CI publishes only a short-lived public RSS text-only Word preview, not original screenshot evidence.

## Acceptance

- Offline regressions cover 08:00 inclusion, 07:59 exclusion, timezone validation, exact end, newest-first across publisher sources, 20 cap, production-default 15 cap, no claims of images/events, and no email/cron.
- Hosted CI must pass offline tests and real RSS preview creation separately; offline tests prove logic, not availability of publisher webpages.
- Gate 23 does NOT close original publisher screenshot issue, protected GitHub Gmail Environment, private R2 storage, Android/Windows apps, or production scheduling.
