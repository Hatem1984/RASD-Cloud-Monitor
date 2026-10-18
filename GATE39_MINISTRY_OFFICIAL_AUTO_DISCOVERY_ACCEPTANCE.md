# RASD — Gate 39: official Ministry source AUTO-DISCOVERY verified

**Evidence date:** 18 October 2026 (Africa/Cairo).  
**Source-discovery subgate:** PASS, original publisher evidence accepted (10 auto-discovered links, 2 first-party reads, 1 current selected screenshot in a Word).  
**Daily production delivery and final multi-source Word:** NOT APPROVED. Those are the next RASD delivery stages.

## What changed from Gate38's HOLD

The official Ministry `/News?id=57&lang=ar` HTML page presented zero regular article `<a href>` links when blocked external trackers/scripts were excluded. Rather than lowering browser safety or inventing article IDs, Gate39 observed the website's own GET request:

`https://mped.gov.eg/News/NewsList?lang=ar&pageNum=1&typeId=0`

The Ministry returned a first-party `text/html` news fragment (about 79 KB). Article cards use `<div id="div_7269"> ... onclick="newsDetails('7269','True',...)"> ...` **instead of conventional anchors**.

The new `discover_official_newslist`:
- Calls ONLY the exact publisher-owned AJAX URL, with explicit HTTPS, `max_redirects=0`, 20-second network timeout, HTTP status=200, exact response URL, `text/html` response and 1.5 MB byte cap.
- Extracts an ID only when an original publisher card `div_<id>` **and** its matching, explicitly named `newsDetails('<same id>',...) ` click-handler both exist. It does not increment, predict, enumerate, import search engine results, or read arbitrary IDs.
- Canonicalizes each discovered URL under `https://mped.gov.eg/singlenews?id=<observed-numeric-id>&lang=ar`, dedupes, caps at 35, rejects foreign host, query variants, malformed bodies and scripted impostors.
- Leaves production `sources.json` and all four saved Ministry phrases unchanged, forbids Gmail, cron, R2 and public Word/JPEG artifacts.

## Real repeatable hosted-runner acceptance

[Hosted CI run 39112559986](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39112559986), exact SHA `1165418535cf871ceb5e41cf2bfe2d7c0c9643c0`:

- **10** genuine original publisher article IDs from its first page.
- **Two independent GETs** to publisher `NewsList`, both containing the independently reviewed original article ID.
- The system did **not** supply the sample link to the discoverer. The sample could only pass after its URL was actually found in the official list.
- The discovered page's published date **17 October 2026** (Arabic original, no fabricated hour) matched the target calendar date.
- **One real browser screenshot of the actual Ministry article page**, original JPEG quality verified, strict screenshot SHA matched the exact embedded Word drawing; original page and the Word remained in runner private temporary storage and were destroyed.
- **217 total Python tests**, one optional/dependency skip; both offline-security and real-public-feed CI jobs successful. No mail, scheduling or public evidence uploaded.

This qualifies the **source auto-discovery and original-page verification** implementation. A few publisher cards were not individually opened or screenshotted in this gate, and the currently approved final Word may not claim that they were. The source remains opt-in until integration into the final all-source report in Stage 2.

## Remaining delivery acceptance

- Integrate the opt-in Ministry news-card source with the Hapi/Al Masry RSS entries in a final dated Word report, with correct event deduplication and complete original-page screenshots for **every included article**. This is **Stage 2** and must fail closed if source health or image evidence fails.
- Validate multiple relevant calendar windows and changes to the Ministry's current-list schema; a first-page list is not a complete historical archive. Coverage status must explicitly show this limitation.
- Gate34 real private archive/R2, Gate35 real Gmail protected transport, owner-approved schedules, multiday full release QA and clients remain separately gated.

**Safe launch boundary:** passing the source-discovery smoke checks does not authorize Gmail delivery, public files, billing, cron, or a production email containing incomplete evidence.
