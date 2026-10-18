# RASD — Gate 36: October 17, 2026 / 25 original-page news experiment

**Experiment executed:** 18 October 2026, Cairo timezone. **Release status: HOLD.**  
**Approved production feed scope:** Hapi and Al Masry Al Youm; Ministry of Planning topics only.  
**Target window:** 2026-10-17 00:00:00 inclusive to 2026-10-18 00:00:00 exclusive (Africa/Cairo).  
**Target:** 25 independently identified publisher article URLs, each with a genuine screenshot of its original publisher page, all bound byte-exact inside a Word QA document.

## Actual hosted public-news evidence

[GitHub Actions run 39108494977](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39108494977) completed both jobs successfully at the same branch SHA. Actual October 17 test output:

| Fact | Observed |
| --- | --- |
| Native publisher feeds healthy | 2/2 |
| Publisher article links inspected in live RSS | 60: Hapi 10, Al Masry Al Youm 50 |
| Valid Ministry of Planning article candidates dated **17 October in Cairo** | **0** |
| Requested count | **25** |
| Original-publisher screenshots captured for qualifying October 17 articles | **0** |
| Real 25-article QA Word created or verified | **No** |
| Acceptance result | **HOLD** |
| Email, scheduler, private storage or public screenshot/Word artifact | **None** |

**Interpretation:** Healthy RSS is not a complete historical publisher archive. Zero qualifying items *returned by the currently available RSS feeds* does NOT prove that no relevant Ministry of Planning stories were published on October 17, or that 25 such stories do not exist online. Neither publisher feed was silently replaced or backfilled by another unapproved source. No historical/newspaper image was substituted for an actual publisher-page screenshot.

## Engineering harness verified separately

- Added `gate36_yesterday_25_qa.py` as an isolated, ephemeral branch-only genuine-page experiment without changing the approved production 15-story strict limit or 20-story preview limit.
- The built-in actual-date QA will only run the following Cairo day and only with the unchanged approved two-source profile. It matches publication **date in Cairo**, not a rolling 24-hour window, and selects at most 25 distinct canonical URLs.
- For each candidate found, it invokes the existing original-page validation and JPEG integrity checks. Only when 25 or more qualifying articles exist, both feeds are healthy, **all** 25 screenshots pass and the DOCX embeds all 25 in the corresponding article order can it return `READY_QA_ONLY`.
- Any shortage, rejected screenshot or source failure produces `HOLD` and no complete QA Word. The only potential Word/photographs are kept in a private ephemeral runner temp directory and are deleted before result emission.
- No real Word/photos/URLs/heads are logged or uploaded. Public audit contains redacted source IDs, counts and failure codes only; Gmail, storage, schedule and billing stay OFF.
- Synthetic offline fixtures exercised 25 and 26 candidates, 24-candidate shortage, damaged publisher page, feed outage, source/profile restrictions and exact Cairo date boundaries. [CI 39108494977](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39108494977): **199 tests total, 1 conditional skip**, both jobs successful. These fixtures are **not** real news evidence.

## Disposition and next safe direction

Keep the pilot branch and review **unmerged**: the real 25-news acceptance is missing, despite sound test machinery. To attempt an actual 25-article historical backfill would require separate approval for a legitimate, reproducible archive/data source that supplies dated original publisher URLs, preferably a publisher-supplied historical feed, while preserving all URL/title/time/image evidence. The existing RASD scope does not authorize silently broadening topic/publisher filters or substituting aggregator thumbnails. No final report should be issued from this experiment.
