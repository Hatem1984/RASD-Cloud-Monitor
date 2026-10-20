# Gate69 — strict original-source health observation (QA ONLY)

20 October 2026 (Africa/Cairo). This stage increases the operator's ability to **detect, diagnose and block** intermittent upstream source faults; it DOES NOT alter how original RSS XML is parsed, repair publisher XML, add alternative publishers, send Gmail, enable R2, change keywords or activate cron.

## Why this stage

Issue #53 documents genuine inconsistent XML from **the exact original Al Masry plural native RSS**. This cannot be fixed responsibly by dropping malformed original items, substituting a different source, filtering the XML payload until it parses or declaring a valid RSS response based on HTTP 200 alone. Existing `monitor.inspect(require_complete_items=True)` already performs a strict full parse, one bounded retry only for explicitly transient conditions and leaves incomplete or malformed sources in `HOLD`.

Gate69 adds:

1. A **read-only real-source probe** of exact configured original Hapi and Al Masry native RSS via the existing strict parser, plus the **publisher-owned** Egyptian Ministry `News/NewsList` discovery adapter. It emits only source IDs, yes/no, bounded verified-link counts, bounded numeric XML error codes; no article URLs/headlines/raw RSS, Word/JPEG, user data or secrets.
2. A pure observation window classifier requiring **seven consecutive different completed Cairo days** with all three original-source states recorded as healthy before emitting `OBSERVED_HEALTHY_7_DISTINCT_DAYS_NOT_UPSTREAM_GUARANTEE`. This *observed* label is NOT a new launch policy, cannot prove future uptime and never grants production delivery. One malformed feed => `HOLD_UPSTREAM_SOURCE`, with no silent source substitution. Healthy feeds with zero matches/items are distinguished from outages; Ministry still needs an original link.
3. A single isolated `gate69-native-source-health-readonly` branch-push probe. No cron, manual Gmail workflow changes or persistently published customer artifacts. It fails safely on any source error; a green probe is only **one instantaneous observation**.

## Genuine evidence and limitations

On the 20 October 2026 live read-only probe [GitHub Actions 39487170908](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39487170908), all 3 ORIGINAL sources were healthy at that observation: **Hapi 10, Al Masry 20, official Ministry NewsList 10**. This does not erase prior October18 original XML code11 evidence nor prove seven consecutive healthy days. Stage2 #42 remains open for actual owner page-by-page review of two independent Cairo-day encrypted original Words (2026-10-17 and 2026-10-19); that review must happen on the owner's machine using Gate61 and Gate62. Upstream source #53 remains OPEN for future observations and incident policy.

Production Gmail, R2, automated scheduler and final source activation are OFF and require their own subsequent acceptance. Do not put a public RSS health snapshot or successful synthetic fixture in the place of a genuine Word or human review.
