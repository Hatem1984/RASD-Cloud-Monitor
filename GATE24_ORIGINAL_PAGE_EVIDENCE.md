# RASD | Gate 24 — real original-publisher screenshot acceptance

**Status:** evidence acceptance path added and tested; the actual live publisher screenshot result must be read from the latest GitHub Actions run. This gate does **not** claim publisher access was fixed.

## Motivation / verified boundary

The GitHub-hosted Chromium can produce valid synthetic screenshots. Real publisher requests have returned `publisher_access_refused` (typically HTTP 401/403), which is a publisher/network-access issue, **not** evidence that Playwright cannot render. No fake screenshots, article photos, screenshot of an RSS snippet, browser identity rotation, proxies, access-control circumvention, CAPTCHA bypass, or publisher anti-bot workarounds may be used.

The original RASD contract requires an authentic screenshot of the publisher's **article page**, with matching publisher URL and title, genuine image quality, and SHA256 identity, before the final Word may be created. The final report must be `HOLD` if ANY included article fails or a source is unavailable.

## What Gate 24 adds

- A bounded **single-article live publisher screenshot acceptance probe** (`gate24_evidence_probe.py`) that uses the existing `proof_capture` strict validator rather than a weaker parallel path.
- Actual news sourced only from the two allowlisted original-publisher RSS feeds. The selector never injects historical references, generated content or a fabricated URL.
- Retry/bypass **not introduced** for HTTP 401, 403, 429 or CAPTCHA pages.
- Temporary genuine screenshot bytes are deleted when the sample exits; **no original publisher screenshot or page text is committed or uploaded as a public artifact**.
- GitHub Actions read-only QA executes one limited actual screenshot proof attempt alongside the existing feed observation and draft Word. Failures are shown using allowlisted codes in a redacted diagnostic manifest; CI success means **execution and safety contract passed**, NOT that a real screenshot passed.
- Result `SAMPLE_VERIFIED_ONLY` means a single original screenshot passed strict checks, not that the full daily report is ready, and **never** sends email or schedules anything.
- `HOLD`/ `NO_ELIGIBLE_ARTICLES` is an honest acceptance result, not a success; full Word and delivery still prohibited.

## Acceptance and exclusions

Run the offline suite: `python -m unittest discover -s tests -v`.

An eligible LIVE publisher screenshot is evidenced only by `verified_screenshots > 0` and a clean verified row in the corresponding Actions job. If `publisher_access_refused > 0`, the publisher refused access and the operational issue remains open.

Do not promote Gate 24 to fully working report delivery until a real complete Word with **every** screenshot and no source outage is independently verified through the full `cloud_proof_report.py`/protected delivery path.

No R2 account, billing, Gmail secrets, SMTP transmission, permanent archiving, persistent daemon, schedule, mobile app or executable is enabled here.

## Next

If repeat real publisher screenshot attempts continue to return 401/403, pursue **authorized publisher screenshot access** or a different *reviewed* original-media source that explicitly permits capture. A different approved news source requires its own provenance review, RSS contract updates and tests; no silent source substitution. The owner is not asked to run Chrome locally as a 24/7 workaround.
