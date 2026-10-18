# RASD — Gate 37 | Stage 1 Ministry news discovery hardening

**Date:** 18 October 2026  
**Product scope:** Egyptian Ministry of Planning only, exact four saved OR expressions in `sources.json`. **Do not broaden to generic economic news.**

## Implemented (source-code acceptance, not full Stage 1 production acceptance)

- Preserved `sources.json` without edits: `وزارة التخطيط`, `وزير التخطيط`, `وزيرة التخطيط`, `التخطيط والتنمية الاقتصادية`.
- Recover matching stories when these exact Ministry terms occur in the publisher's **native RSS short description** but not its title. This is limited to the already allowlisted original publisher feed and article host. Strip RSS markup, decode HTML entities, normalize Arabic diacritics/tatweel/common Alef variants *for matching only*; original headline and text are kept for Word. Preserve word boundaries and reject generic economics without the saved phrases.
- Audit separate source counts `description_matches`, `native_description_matches`, and `rss_feed_is_exhaustive_archive: false`. Original legacy `planning_headline_matches` is retained for compatibility, even when a native description supplied the keyword.
- Accept a timezone-aware ISO-8601 Dublin Core `dc:date` **only if original `pubDate` is absent**, converting into a timezone-aware RFC-2822 timestamp for existing downstream validators. Do not guess UTC for naive timestamps, silently replace malformed publisher `pubDate`, or use RSS fetch time as publication time. Keep stricter final proof gates.
- Added isolated tests for both approved production feeds, all saved expressions in publisher descriptions, non-Ministry exclusions, title priority, timezone-aware ISO, invalid/old/future/ambiguous dates, external links, metadata, and the Cairo 17/18 October midnight boundary.
- Corrected an older state-replay test to use a **dated native publisher fixture**, rather than treating an undated hypothetical link as a production-valid article.

## Publisher/source review

1. **Current approved production**: Hapi `https://hapijournal.com/feed/` and Al Masry Al Youm `https://www.almasryalyoum.com/rss/rssfeeds`. Both are native publisher-owned feeds. Their current rolling RSS items are **not** a comprehensive historical index; a previously missing October 17 story cannot be inferred absent from the web.
2. **Already reviewed separate opt-in**: Al Shorouk economy RSS `https://www.shorouknews.com/Economy/rss`, with its own `sources_shorouk.json`, historical source-limited original-page capture acceptance. It remains **OFF** for production as previously agreed; opt-in alone cannot certify every article's screenshot and full source coverage.
3. **Official Ministry publisher**: `https://www.mped.gov.eg/singlenews?id=7246&lang=ar` shows a dated 8 October 2026 original ministry story. This is a promising **candidate for an independent official-source connector**, but it is **NOT** included in the code's allowlist. Require a bounded, publisher-controlled canonical news archive/endpoint, explicit publication-date verification, allowlisted domain, independent original page screenshot and reliable acceptance tests before promotion.

## Verified vs pending

**Gate 37 code checks:** see branch CI and regression evidence in PR. Code completion can be closed independently after the latest CI is green.

**Stage 1 full production acceptance is still HOLD** until real sustained source-wide discovery and original-page screenshot-backed Word are verified over repeat windows. Native RSS descriptions may recover missed relevant headlines but do not solve expired RSS history, publisher access refusal, missing news archive or 25-story historical quotas. No source added, Gmail activated, storage provisioned, cron enabled, PDF generated, public screenshot posted or production article limit enlarged.

### Completion criteria before declaring Stage 1 at 100%

- Demonstrate a reliable selection of dated original Ministry stories across reviewed, approved original publishers; distinguish empty RSS feed, source outage and true filtered zero.
- Qualify additional original news archive/feed including any future official ministry connector **without expanding keywords/topics**, using explicit security/coverage tests.
- Repeat cloud-browser original article-page capture checks and a complete per-article JPEG-to-Word SHA-256 validation on all selected articles, with fail-closed HOLD on missing evidence.
- Document clear source-level coverage, anti-duplicate behavior and actual dated reporter vs publisher timestamps; never claim whole-web completeness.

**Next stages:** 2 final Word acceptance; 3 private evidence storage; 4 protected Gmail; 5 owner-approved schedules/alerts; 6 multi-day release QA; 7 authenticated API and desktop/mobile clients if required.
