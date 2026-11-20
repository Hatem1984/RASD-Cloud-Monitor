# RASD — 100 effective sources and hourly/final Word parity (review gate, 19 Nov 2026)

## Actual scope before this change
- Production inventory remains **13 approved native RSS endpoints**, with **29 approved planning phrases**.
- A separate research catalog contains **100 origin identities**, of which **87 are not scheduled**. This catalog is NOT evidence that 100 websites can be monitored.
- A successful fetch, a valid RSS file, a relevant story, an original-page screenshot and accepted delivery are **five different gates**. Never collapse them into one success count.

## Changes prepared, NO production activation
1. Existing scheduled interval news with genuine publisher screenshots uses the **same Ministry navy/gold cover, editorial analysis, site distribution and original screenshot card structure** as the 22:00 final daily Word. Text distinguishes interval/new captures from previously delivered daily archive originals.
2. Source-limited hourly Word states the actual failed-feed count and number of image-HOLD items. No unavailable source or image is reported as a verified story. Daily historical report semantics and private archive paths are not rewritten.
3. A standalone bounded public-first-party RSS preflight can inspect the **100 already catalogued origins**, reading safe HTTPS endpoints without following redirects, and classify each as:
   - \`RSS_MATCH_PENDING_ORIGINAL_PAGE_IMAGE_QA\`: native dated RSS with a recent saved-ministry-term match; STILL NOT a confirmed original-page image.
   - \`RSS_VALID_NO_RECENT_MINISTRY_MATCH\`: native feed parsed; NOT proof of useful Ministry news.
   - \`HOLD\`: unavailable, malformed, cross-domain, undated or not qualifying; no fabricated success.
4. A separate owner-triggered/manual read-only GitHub workflow is included. It cannot send mail, change production scheduled feeds, grant source approval, write private storage, or upload article screenshots.

## 100-source target (NOT YET MET)
A source counts toward the owner's **minimum of 100 operationally useful sources** only after:
- unique publisher identity and approved scope;
- repeatedly reachable original source feed or verified public official API;
- native link/title/original publication time verification;
- a real, relevant Ministry item where published, with approved host;
- genuine original article screenshot and JPEG/Word binding checks;
- repeated operations and explicit controlled production enablement.

Preflight results indicate **research readiness**, never production-ready sources. If reaching 100 needs more than the present 100 research origins (for example, screening ~1,500), collect and review an expanded origin list separately. No 1,500-site search has been executed or certified in this branch.

## No-send check
Run offline tests via \`python -m unittest discover -s tests -v\`; the gate CI also runs public publisher no-send checks. The separate research audit can be triggered intentionally after branch review. **No SMTP, cron, recipient, private ledger, archive or source-allowlist writes** are part of this gate.

## Release criteria
Keep this work in a PR for review; do not claim \`100 successful sources\`, a completed Ministry report or actual email delivery until real source-by-source evidence supports each claim. Production changes and any cost-bearing services require owner approval.


## 20 Nov owner correction — HOURLY production, 6–7 real relevant news items per hour target

- Output: at most one production news email per hour, not two. Keep redundant original-source scan opportunities, but hourly reporting is eligible only in first half of each hour. One private CAS write atomically reserves the hourly slot and all included news article IDs; an uncertain slot is never blindly retried.

- Period: previous completed UTC/Cairo clock hour. Relevant previously unsent 72-hour backlog may also be recovered, with original publication dates still shown; news published since current hour boundary is deferred to the next report.

- Cairo 22:00 is still the daily rollup window, not an extra competing hourly email. A final-hour story can be picked up by the next hourly scan, so perfectly uninterrupted hourly mail is not yet proven.

- Visual contract: hourly Word uses the final Ministry navy/gold cover, analysis, distribution and original JPEG/link cards. Explicit title: تقرير المتابعة الساعية. It does not claim current images were previously delivered.

- News target 6–7 per hour: performance objective, NEVER a fabrication or unrelated-news quota. Source health, exact original publisher date and original image remain mandatory. Read-only source audit now reports previous complete-hour RSS match volume without treating this as delivered news.

- Capacity HOLD: 6–7 news cards per hour imply 144–168 per day, while current daily rollup is capped at 60 stories and Word at 8MB. No auto-lifting, hidden truncation, historical edit or invented photos. A separately reviewed multi-volume daily archive design is needed before claiming complete daily rollup at this rate.

- Deployment: production steps stage environment flag RASD_HOURLY_REPORTS_ENABLED=true for reviewed merge. Source list, 29 original phrases, recipients, SMTP, private CAS data, existing cron expressions and Cloudflare identities are unchanged. No production merge or live email test.
