# RASD — Evidence-based status of the four owner-raised gaps — 20 Nov 2026

**Overall decision: PARTIAL REMEDIATION — PRODUCTION HOLD.** Never claim the 6–7 fresh relevant original-photo items/hour or 100 working sources requirement achieved; neither is supported by authentic source evidence.

## 1. Validated repairs (Draft PR #189 only)

| Owner issue | Actual code repair | Independent evidence | Production status |
|---|---|---|---|
| Hourly Word must match daily | One formal navy/gold cover, Arabic analysis, publisher distribution, original JPEG cards; hourly originals distinct from recovered older coverage | 7-image SHA & cross-layout offline fixtures | NOT MERGED |
| New hourly cards lost by daily rollup | New `rasd_daily_grid_extractor.py` validates numbered table-cell article identity, original headline, publisher, date, URL relationship and embedded JPEG digest, then reconstructs daily Word through the mock Sent/MIME production path; old paragraph-style Word remains supported | CI passed; [run 44787577541](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44787577541) | NOT MERGED |
| Daily 60-item limit | Bound changed to 180 coverages and 15 MB only for day-end Word; keep hourly 8 MB; add 168 distinct exact SHA synthetic image stress and explicit HOLD for 181 | [run 44788310245](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44788310245), 751/751 | 15 MB daily original real photo success not yet proven |
| Hourly versus Cairo 22:00 daily collision | Preserve 22:00 daily; only allow hourly news within Cairo 22:30+ to cover the preceding 21:00–22:00 interval. Hourly CAS reservation remains per hour and no duplicate SMTP retry. Accepted-after-cutoff news is included in next day's 22:00 daily, without retroactive change | summer/winter DST and 22:37 activation tests; [CI 44791247461](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44791247461), 753/753 | NOT MERGED, not actually sent |
| Source discovery stalled on native RSS only | Added read-only strict original publisher Atom and HTML research, bounded safe source HOLD reason classification and first-party browser photo QA | Linked research/live runs below | Only one new source fully staged |

## 2. Real publisher read-only audits

- [Full strict 14-source shadow scan 44791472896](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44791472896): **13 of 14 configured RSS sources parsed successfully** on Nov 20; **8 on-scope RSS links in the prior 72 hours**, not 8 proven hourly articles. **1 of 1 newly qualified Al Nahar originals** passed the existing actual screenshot pipeline. The source inventory is **14 only on the draft branch**; production `main` still has **13**.
- Al Nahar: original `https://www.alnaharegypt.com/feed/` was inspected, source-accurate dates/links parsed, and screenshot of original page verified. Staged `alnaharegypt` as a 14th feed in Draft branch with original publisher, RSS and official Word label mapping; no production activation.
- [Original-photo browser QA run 44789145206](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44789145206): Al Nahar and Youm7 original screenshots PASS; Ahram gate publisher REFUSED, correctly HOLD. Later 4-publisher run logs included Al Mal image PASS, but cannot alone approve HTML discovery/sending.
- [Original Al Mal HTML research 44792935918](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44792935918): article discovered from publisher homepage and verified against first-party H1 and timezone-bearing article:published_time. Initially failed on an unencoded Arabic URL path, then passed after standards-compliant UTF-8 URL quoting; 1 original page validated, 0 HOLD; **research only, not activated**.
- [Original Al Mal RSS research 44792030288](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44792030288): tested four apparent same-site RSS routes; **0 passed the strict full-item parser**; the HTML path above is a candidate solution, but not automatically approved.
- Youm7: a genuine original-page screenshot passed; strict native RSS path remains malformed. No unverified feed activated.
- [Original Al Masry Alyoum RSS alternate read-only test 44791727945](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44791727945): current endpoint and Egyptian section both passed strict full-item parsing on a later retry, showing an **intermittent malformed-feed failure**, not permission to invent/repair publisher XML. At full 14-source scan the source was HOLD `rss_xml_malformed`.
- Historical 100-source investigation has shown many endpoints missing, rate-limited or blocked. **100 truly end-to-end capable sources NOT established**.

## 3. Read-only Inbox reality check (without displaying credentials)

The authorized connected inbox contained actual original Word reports received on Nov 20 at **15:30 and 16:30 Cairo**, each with **one authenticated pictured publisher news item** and partial coverage notices; actual Nov 19 daily formal Word had **three clippings across three websites**. In current sends a relevant Hapi green-projects original page was `publisher_access_refused` and NOT silently accepted. These are genuine deliveries from **old production** only; they do not prove the Draft hourly visual Word or new source reaches the ministry Inbox.

## 4. Remaining HOLD / evidence required for final closure

1. **6–7 original verified new on-scope stories EVERY hour:** not a guaranteed fact about publishing volumes. Source discovery must be widened and real multi-hour fresh candidates and screenshot success counted; do not meet quota via repeated or old stories. The known run showed 8 on-scope original RSS matches in 72h across 14 configured feeds.
2. **100 actually working sources:** not proven. Only one additional source reached strict feed+date+original-photo on branch. Al Mal HTML and Youm7 screenshot are promising but do not constitute ongoing production-approved monitored sources.
3. **Daily attachment 168 actual JPEGs under envelope and real Gmail acceptance:** static 168/15 MB fixture passed, but variable real photo sizes and Gmail/recipient acceptance remain unverified. Overweight remains explicit HOLD rather than truncation.
4. **Actual changed hourly SMTP + recipient inbox delivery, hourly stability and exact daily inclusion:** cannot assert, new branch is UNMERGED; do not send real mail as part of no-send testing; requires a reviewed production release and observation on known authorized recipients.

## 5. Security and ownership

- PR [#189](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/189) remains Draft; all owner-approved recipients, secrets, Cloudflare dispatch identity, private archive, CAS and existing main production schedule remain unchanged.
- Browser photo artifacts are ephemeral; no unapproved publisher restriction is circumvented; the Ahram original 403 stays HOLD.
- Tests are synthetic and mock delivery, unless explicitly identified above as real first-party read-only or existing Inbox observation. No new SMTP sent by this work.
- Last cross-suite offline CI after adding publisher HTML QA: [run 44792947100](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44792947100), **757/757 PASS**.
- The precise access to the owner's local Windows machine was unavailable (Desktop Commander offline).

**Final status: verified code corrections and one staged additional working source; the owner's four end-to-end production requirements are not all closed.**