# RASD Gate 42 — visual-render QA and independent Cairo-day source windows

Date: 18 October 2026. **Pilot: Ministry of Planning only** with the exact saved four Arabic search phrases and unchanged approved Hapi/Al Masry RSS profiles. This gate is isolated read-only QA, **not production delivery**.

## Implemented protections

1. **Original publisher image fitting**: `daily_report.render_docx` retains original JPEG bytes and its SHA-256 within the Word, constraining BOTH image height (6.2in) and width (5.6in) while preserving aspect ratio and centering the paragraph. Long full-page screenshots previously could exceed printable Word page height when only width was constrained.
2. **Actual document rendering preflight**: `word_render_audit.py` renders the DOCX privately using LibreOffice to a temporary intermediate PDF, rasterizes all pages with Poppler, checks embedded image dimensions/count and rejects empty or unreadable/blank page rasters. All Word/JPEG/PDF/PNG data remain **inside the ephemeral CI runner** and are removed; no public artifact is uploaded. This is **automated preflight, NOT human visual approval**. Production deliverable remains Word only.
3. **Offline layout regression**: tall and landscape synthetic JPEGs in one Arabic Word, physical proportions/placement and original image SHA-256 preserved. These synthetic tests never masquerade as original publisher proof.
4. **Real-day checks**: branch-only cloud test separately inspects previous and current `Africa/Cairo` calendar dates (current day is PARTIAL). Each either renders the full real screenshot-backed Word or returns HOLD with **zero** incomplete Word. No padding or invented news.
5. **Archive cutoff correctness**: when any original Ministry article on a page cannot be dated, that page must not certify `OLDER_THAN_TARGET`; the whole report stays HOLD with `UNVERIFIABLE_PAGE`.
6. **Source resilience without bypass**: one bounded retry only on genuine origin HTTP 502/503/504 or known timeout/connection failure; never retry 403, 429, redirects, mismatched hosts, challenges, or malformed source HTML. Logs emit a strict allowlist of error categories, not articles/URLs/secrets.
7. **No source/recipient activation**: `sources.json`, selected article cap 15, Gmail, R2, cron and production delivery remain unchanged and OFF.

## Actual CI evidence

- [Run 39118789567](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39118789567): both jobs green; synthetic true LibreOffice PDF-to-PNG layout preflight completed on **3 rendered pages** with **2 distinct JPEGs**, no all-white pages, no artifact. Real Oct17 and partial Oct18 checks returned HOLD because original publisher proof/discovery was temporarily unverifiable or there were no qualifying target-day stories in the available sources. The correct result was **no Word and no send**. These runs DO NOT prove stable real-date reporting or human-reviewed final formatting.
- Source index pages 1 and 2 were independently observed returning distinct publisher article cards through a separate read-only page fetch, but that does NOT override GitHub Actions source-health failures.
- The later branch head includes stricter date cutoff and safe bounded origin retry; refer to final-head Actions result and document exact real outcomes before claiming acceptance.

## Exit conditions for Stage 2 at 100% — STILL OPEN

- [x] Real Word with source-original screenshots SHA-verified and bounded Ministry paginated date coverage was proven for October17 in earlier Gate40/Gate41 live runs (historical evidence, not current consistency).
- [x] Word image width/height clipping prevention and **synthetic** private multi-page render preflight code and regression tests.
- [ ] Genuine original-publisher Word produced in **multiple independent live-day windows**, with 3/3 healthy sources and no incomplete article; reports must stay HOLD if a source is down.
- [ ] **Human visual inspection** of EVERY rendered page in the complete authentic report for Arabic shaping, clipped text, source dates and image legibility. A structural hash or synthetic render test does NOT substitute.
- [ ] Formal activation of the official source in the approved daily collection workflow with monitored retries, full proof and recipient gates; NOT equivalent to enabling Gmail.
- [ ] Final output original Word privately reviewed, never uploaded as plaintext in public Actions.

No Gmail, auto-schedule, R2 paid storage or public Word/JPEG artifact was enabled. Stage3 storage, Stage4 Gmail, Stage5 monitoring/cron, Stage6 final multiday launch acceptance, Stage7 apps are subsequent distinct stages.
