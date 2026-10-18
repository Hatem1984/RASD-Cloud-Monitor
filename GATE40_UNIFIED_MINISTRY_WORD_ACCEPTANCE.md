# RASD — Gate 40 | Stage 2 unified Ministry Word evidence, guarded QA

**Date:** 18 October 2026.  
**Production source profile:** UNCHANGED. Two original publisher feeds (Hapi, Al Masry Al Youm) remain in `sources.json`, four Ministry of Planning phrases remain EXACT and no generalized economic reporting is permitted. Official Ministry is **opt-in to this Stage 2 QA runner only**, not activated for scheduled production/delivery.

## Implementation

- `unified_ministry_word.py` reads the existing two approved RSS sources via the existing monitor and article candidate/host/date gates. It separately discovers original Ministry news via its validated same-origin AJAX `NewsList` adapter. The Ministry page link inventory must be **identical in two independent reads**, with no guessed IDs or external aggregation.
- Targets **one exact local Cairo calendar day**, either the current or previous day, with explicit `Africa/Cairo` timezone; rejects stale historical days. Every RSS article retains its original timezone-aware minute. Official Ministry pages expose only an Arabic calendar date: **a nonexistent publication hour is never fabricated** in the Word.
- Reads original official article page and headline/date first to exclude out-of-window cards, and captures every **included** official article from the same original publisher domain. Existing `proof_capture` guards capture original RSS publisher article pages. No synthetic screenshot passes live acceptance.
- Merges original sources into one **unique canonical URL** inventory, retains publisher provenance and original dated headline. Different publisher coverage of the same event is **not falsely asserted to be multiple independent events**; event-level semantic dedup is not yet certified.
- Strict production 15-article cap is **not widened**. If more than 15 original qualifying links are detected, the pilot fails closed instead of truncating a supposedly complete report.
- If any selected article's JPEG is missing, image hash differs, a source is down, the Ministry index changes mid-run, a publisher page has no original date, or Word's corresponding drawing is altered/reordered, **NO unified Word is issued** and `HOLD` is reported.
- If all selected URLs, sources and JPEGs pass, creates **one Arabic Word** with every genuine original publisher screenshot, and re-verifies ZIP relationship order and embedded SHA-256 digests against the captured images.
- One intentionally bounded official `NewsList` front-page snapshot (**first page only**). The system does not claim exhaustive coverage of the official Ministry archive or the internet. A complete multi-page ingestion and extended repeated live windows remain required before final release.

## Safety guarantees

- No real Gmail SMTP send, R2/private storage write, approved-recipient change, scheduled jobs, public article JPEG or public complete Word CI artifact.
- The Word is held only inside a temporary GitHub runner directory during manual QA; it is NOT uploaded to the public repository or Actions artifacts.
- Existing historical 25-news experiment remains `HOLD`: it does not justify finding unrelated general economic articles.
- The redacted audit includes counts/status/reason classes only, not publisher article body, owner email, URLs of unreviewed stories or screenshots.

## Stage 2 acceptance gates

1. **Offline synthetic original-publisher fixtures:** merged RSS+official JPEG-to-Word with exact matching image bytes, correct day-only official publication, duplicate suppression, 15-item cap, source failure/HOLD, publisher screenshot failure/HOLD, index instability/HOLD and zero news/HOLD. This is engineering regression coverage, not live acceptance.
2. **Hosted real public source smoke test:** same-source date 17 October 2026 for the official Ministry page and currently available native RSS (within 72-hour horizon). A Word can be QA-ready only when **every selected** genuine article has a verified original JPEG inside the final Word; any shortage remains HOLD with no document. Distinguish a healthy-but-empty original RSS feed from a failed RSS provider.
3. **Production approval still OPEN:** whole first-page and paginated official Ministry source coverage, enough independent real dated report windows with nontrivial RSS+official matches, separate visual review of the entire completed Word (not only ZIP SHA checks), formal source activation, and then private storage/Gmail/scheduling through their own safeguarded gates.

**Result classification:** `READY_QA_ONLY` is an isolated proof, not approval to send or schedule production Word. `HOLD` is expected for unavailable/undated original stories and prevents publishing.
