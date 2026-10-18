# Gate 41 — verified original Ministry pagination and Cairo-day cutoff

Date: 18 October 2026. Source scope remains the four saved Ministry of Planning phrases and two native RSS feeds, plus the separately qualified official Ministry source.

## Real cloud acceptance

Evidence: https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39116940080

- Official NewsList source pages checked: **2**, two independent and identical GET results per page.
- Original article URLs confirmed: **20**.
- Official pages dated before 17 October 2026: **19**, based on original publisher article pages, not crawling time.
- Official original-page article matching 17 October: **1**.
- Hapi native RSS matched: **1**; Al Masry Al Youm RSS healthy but no eligible item.
- Final single Arabic Word: **2/2** real original-publisher JPEGs, exact ordered SHA-256 image relationships, no missing screenshot, all 3 sources healthy.
- The full second page was dated strictly older than target day, validating the **OLDER_THAN_TARGET** stop condition.
- QA result: **READY_QA_ONLY**. No production activation, no public document or JPEG artifacts, no Gmail, R2 or scheduling.
- 235 offline tests total, one conditional skip, both CI jobs success.

## New bounded source rules

Publisher endpoint is the already observed official GET /News/NewsList?lang=ar&pageNum=N&typeId=0. Allowed pages 1 through 4, exact first-party URL, no redirect, HTML type and response size bounds. Each page list must match in two independent reads; card IDs must come from real publisher markup, no ID enumeration or arbitrary query.

Every dated original article is inspected before ending the scan. An older-than-target complete page or truly empty publisher page is required to stop; no assumed completion after page one. A duplicate page, chronological inversion, invalid original date, failed source or unproven cutoff at the fourth page rejects the complete Word with HOLD.

## Final acceptance boundaries

This Gate 41 paginated QA is proven for the real Oct17 publisher inventory; it does **not** prove exhaustive historical coverage of every news event across the web. **Visual inspection of a rendered complete Word page** and independent live daily windows remain unapproved. Stage2 production release stays OPEN. The saved four Ministry keywords and two RSS sources remain unchanged.

## Follow-up source-stability incident

A later independent hosted run [39117275922](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39117275922) verified the **same two-page/20-link original Ministry date boundary**, but the unrelated Al Masry Al Youm original RSS feed failed to respond. Safe outcome was **HOLD with no Word**, even though the official Ministry screenshot was valid. This does not invalidate the earlier successful source-proven Word QA, but it explicitly prevents claiming continuous production coverage or Stage 2 = 100%. Later CI distinguishes a safe external outage/HOLD from a code regression; both outcomes remain visible in redacted logs.

## Public CI evidence privacy repair

Inspection revealed legacy manual Actions flows that publicly uploaded an original-publisher JPEG folder or an unencrypted Arabic Word preview; Stage 2 privacy hardening now removes these upload steps in capture-manual.yml and report-manual.yml, as well as the automatic branch CI preview upload. Publisher JPEGs and Word remain only in the runner's short-lived work directory. The separately reviewed owner-encrypted JSON-only pilot and sanitized JSON manifest uploads are preserved. Static regression tests reject future unencrypted Word/photo artifact paths.
