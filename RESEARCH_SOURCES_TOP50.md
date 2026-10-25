# RASD — 50-source research registry (2026-10-25)

## Purpose

This catalog supports Ministry of Planning newsroom research. It is intentionally **not** a 50-feed production activation. The **thirteen** verified feed endpoints now included, replacing the prior thirteen exact approved original RSS publishers and **24** saved phrases remain unchanged. All remaining 37 research origins need source-specific engineering validation; no search snippet or secondary image is accepted as original evidence. Do not send email or trigger any scheduled workflow merely to validate the list.

## Interpreting the ranking

- Positions 1–4 honor owner-prioritized established national newspapers: Al-Ahram, Akhbar El Yom/Al Akhbar, Al-Gomhuria, Al-Masaa. This is an **editorial research priority**, not a fabricated traffic/credibility ranking.
- Positions 5–24: large-reach and established Egyptian general news, agency and periodicals.
- Positions 25–39: economic, English-language, independent and specialist coverage; useful for Ministry of Planning policy, investment and growth.
- Positions 40–45: selected international and regional coverage for independent corroboration of Egypt-related events.
- Positions 46–50: first-party Ministry / National Planning Institute / Cabinet Information Center / CAPMAS / State Information Service. These are **primary documentary checks**, not proof of editorial independence.
- `similarweb_egypt_news_rank_aug_2026` is populated only for the five exact Egyptian top sites where free published evidence exists; `null` is unknown, not low readership. Readership does not imply truthfulness. Common parent-company / syndicated coverage is recorded by `editorial_group`; two editions do not prove two independent confirmations.

Published evidence: [Similarweb Egypt News August 2026](https://www.similarweb.com/top-websites/egypt/news-and-media/), [AkhbarMeter publisher monitoring](https://akhbarmeter.org/publishers), [SCImago media rankings](https://www.scimagomedia.com/rankings.php?country=Egypt), [Egypt national archival publishers](https://torath.gov.eg/providers).

## Use

Run offline on an existing authorized source checkout:

```bash
python research_source_queries.py --limit 50
python research_source_queries.py --official-only
python -m unittest tests.test_research_sources_top50 -v
```

The generator prints 50 **site-scoped query suggestions**. It makes **zero web/SMTP/GitHub/private-ledger requests** and therefore does not assert that any of the 37 candidate origins has actually been searched, fetched or monitored. Search engine operator behavior varies; query results MUST be independently opened at the original publisher, screened for relevant title/description, publication time and exact article page with correct image. Never substitute search result metadata for publisher evidence.

## Source admission gate

Before enabling any of the 45 candidates as a scheduled production feed:

1. Prove identity of publisher, exact HTTPS feed or documented owner-authorized alternative, stable original article host and no unsafe redirects, and acceptable source access.
2. Verify publisher article timestamp with explicit time zone and complete original article/source-screen capture (including loaded photo), using existing fail-closed behavior.
3. Confirm Ministry-of-Planning relevance in original headline or description, preserve material criticism, suppress unrelated generic finance/sports and duplicated syndication.
4. Run scoped offline tests, CI, staged no-send live collection, private idempotency, screenshot-Word acceptance and an expressly authorized Gmail test. Record exact source activation state, SHA and dated evidence.
5. Only then add the source to `sources_newsroom_active.json` and its immutable endpoint/domain allowlists; never label an unproven source ACTIVE to reach an arbitrary count.

This source inventory itself must not modify active RSS, `monitor.py`, private RASD-Pilot state, schedule or Gmail.

## 25 October 2026 production feed qualification

On authorized Windows (read-only feed checks, no redirects) eight further first-party RSS profiles returned HTTP 200, fully parsed as XML/RSS, exposed original-publisher article links and explicit timezone-aware publication dates. Their exact endpoints are in sources_newsroom_active.json; each article must still pass the original browser screenshot and identity QA or it remains unsent HOLD. Only the National Planning Institute sample passed a genuine original-page visual capture in this qualification session. Remaining screenshots, production cron and recipient Word visual acceptance for the eight newly onboarded feeds remain open; 36 catalog origins are not active feeds. No added Gmail or storage permissions.

Operational smoke scan on 25 October 2026 with strict complete original RSS item checks: 13/14 candidate feeds passed, 217 first-party RSS links counted and six keyword matches. Enterprise Egypt native feed failed the strict check with ValueError, so it is NOT activated (candidate-only) pending diagnosis. No email or ledger writes during this QA.
