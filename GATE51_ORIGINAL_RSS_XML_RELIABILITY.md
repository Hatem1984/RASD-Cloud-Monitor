# RASD Gate51 — official native RSS intermittent XML reliability

**Date 18 Oct 2026.** Ministry of Planning ONLY, exact four saved Arabic phrases, existing approved RSS original URLs unchanged, and the verified first-party Ministry source unchanged. No publisher-to-aggregator substitution.

## Live diagnosis

- Earlier real cloud Word attempts intermittently returned `ParseError` from `https://www.almasryalyoum.com/rss/rssfeeds`, even though other publisher sources passed. Such attempts **properly returned HOLD without Word**; do not claim a missing source is healthy.
- [Publisher metadata-only real diagnostic run 39126841460](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39126841460) and [39127033454](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39127033454) observed the **exact same approved native URL** returning HTTP 200, `text/plain` MIME but **valid XML/rss root**, 20 channel items, 14,893 bytes. A text/plain MIME does NOT invalidate actual XML body. Hapi original RSS was also healthy (10 items). No raw headlines, original HTML, article URLs or secret response data were emitted into public CI.
- HTTP 429 remains a non-retriable publisher rate limit, 403 and redirects forbidden. No SSL or browser challenge bypass, no arbitrary external endpoints, no changing `sources.json`, no invented pubDate.
- Source data is not repaired if XML is malformed: do not replace `&`, strip illegal elements, or accept a subset of items. Successful feed state is granted **only** after complete strict XML parsing and original approved publisher link and date filters.

## Narrow resilience change

Previous two-attempt mechanism retried malformed XML immediately, potentially receiving the same transient upstream response. Gate51 inserts exactly **1.25 seconds between the first full XML ParseError and the existing one permitted retry**. No extra retry count, no replay of old feed cache or accept-on-failure fallback. If second publisher response is not valid full RSS, the source remains failed and **unified Word is HOLD**.

A redacted Boolean `rss_parse_retry_delayed` may appear in source diagnostics; this is not an indication of final source health. Offline tests ensure an original feed that becomes valid on its second read is accepted, while two invalid responses remain failed without fabricated articles.

## Acceptance boundaries

Gate51 security/fault-handling can be merged after CI and live smoke safety tests, but it is not proof of two distinct complete reporting days or human-reviewed real Word. Stage2 Issue #42 must remain OPEN until owner/authorized reviewer decrypts **actual** Word plus all individual encrypted page PNGs, reviews Arabic shaping/date/source/screenshot visually and signs off, and a **second distinct fully completed Cairo day** has a fully sourced strict Word report (3/3 source health; genuine publisher image per article). October 18 is **not fully completed until Cairo Oct19**. No email, R2 object write, automatic cron or public Word/JPEG/PDF/PNG.
