# Gate 52 — safe classification of intermittent original publisher XML parse failures

Date: 18 October 2026. RASD still monitors the **Egyptian Ministry of Planning only**, with unchanged exact four saved phrases, original Hapi + Al Masry Al Youm publisher RSS endpoints and the already qualified first-party official Ministry news source.

## Actual incident motivating this gate

Historical real full-day Word executions have oscillated: the SAME Al Masry native RSS endpoint served valid RSS containing 20 original publisher links in independent metadata-only cloud checks [39126841460](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39126841460), but a later actual complete original Word run [39127245770](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39127245770) returned `ParseError` even after one retry separated by 1.25 seconds. Original Hapi and official Ministry remained healthy in that run; Word correctly remained **HOLD**, and the owner-only ciphertext contained an audit only. A delay alone cannot be claimed to cure corrupted publisher XML.

## Engineering diagnostic added (bounded and redacted)

`monitor.inspect` now retains safe machine-readable metadata **only if original RSS XML is malformed**:

- Expat numeric XML parser `code` (bounded 1–99), first invalid `line` and `column` (bounded), total bounded response byte count;
- Boolean flags for whether the input visibly begins with HTML or RSS/XML;
- Boolean `identical_bad_xml_on_retry` indicating whether the two rejected XML bodies had the same in-memory digest; the actual SHA digest is NEVER logged.
- There is never any raw XML, original article title/link/body, server response body, unbounded exception string, external URL or private key in public audit output.
- The unified Stage2 daily Word log propagates the bounded metadata for FAILED feeds only; the good source remains unaffected. No data is persisted outside redacted CI audit, no new caching or stale-story fallback.

## Strict rejection policy remains

- Invalid publisher XML is never heuristically patched and bad `<item>` entries are never silently dropped. An ET.ParseError must fail closed if the already permitted 2 total attempts cannot parse **the complete native RSS**.
- A rate-limited HTTP429, HTTP403, redirect or unreviewed endpoint remains blocked without retry. No new source endpoints, no changes to `sources.json` or stored Ministry keywords.
- Official Ministry original article date and original-page screenshot validity remain mandatory; only ONE report Word with an original screenshot per qualifying article is eligible.
- All Gmail, cron, R2/private storage, billable hosting, public Word/JPEG/PDF/PNG delivery remain OFF.
- Owner-only RSA/AES-GCM encrypted review Word and 1600px page PNGs are allowed **only when** all sources healthy, original source proofs pass, and rendered Word preflight passes. An all-source degraded day has audit-only ciphertext.

## Acceptance status

This gate measures *why* the publisher feed is failing, not a claim of its recovery. A branch-only real source diagnostic run should be recorded with its exact `xml_error_code` and `identical_bad_xml_on_retry` if it fails. Stage2 remains OPEN until: (1) a real full-day publisher-complete Word for two distinct Cairo dates and (2) genuine private Word visually reviewed page-by-page by the owner/authorized reviewer. No synthetic test, safe HOLD or metadata is a substitute for either.
