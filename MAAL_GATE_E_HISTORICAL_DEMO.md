# MA'AL Gate E — historical official-source impact MVP (owner-only)

## Scope (strict)
- Real source: https://mped.gov.eg/singlenews?id=7269&lang=ar
- Publication day: **17 October 2026** (original source publishes no hour).
- Prior RASD Gate 38 independently verified original article/photo/Word in ephemeral CI. This Gate E **rechecks** live original page in an isolated owner-controlled manual run; never treats historical sample as fresh alert or newly discovered current news.
- Synthetic Egypt infrastructure/renewable-energy SME. This is **not** analysis of any real client or claim that funding is available.
- Topic assertion is made only if original page BODY discusses an infrastructure financing guarantee; no other claim is inferred or backfilled.

## Execute (owner workstation, no secrets)
From root of this branch, with Python/Playwright/Pillow/python-docx installed:

```powershell
python -m maal.manual_official_demo --output-dir "D:\\MAAL_OWNER_QA"
```

Expected success: `HISTORICAL_VERIFIED_DEMO`, verified original JPEG, SHA-matched DOCX, JSON decision brief, date-only precision, no outgoing messages.

Expected access failure: an explicit `HOLD_NO_DEMO` or error — never substitute a synthetic screenshot or infer unknown publisher data.

## Provenance and impact boundaries
- `official_ministry_source._read_original` from the existing RASD pipeline checks exact official URL, original headline/claim, published day and publisher screenshot before marking `verified`.
- `maal.impact_mvp.interpret_official_signal` checks receipt, article ID, original page content phrase, original JPEG bytes/sha, synthetic context, and Gate D `draft_decision_brief` evidence/action contracts.
- Conditional hypothesis: official discussion could matter to a renewable-energy/infrastructure supplier **if** a later financing policy and company eligibility are actually confirmed. No price, benefit, access, credit score or monetary effect invented.
- Only `draft_task` and `draft_report` proposals; human review required.
- Image embedded in DOCX is mechanically SHA-identical to the verified JPEG. Independent human visual review of Arabic page rendering remains pending.
- This rule-based MVP is NOT the promised autonomous agent, an LLM-based business forecast, an approved customer analysis, or production monitoring.
- All proofs stay in a local directory OUTSIDE the Git repository; do not publish the JPEG/Word privately or publicly except through approved encrypted owner process.

## Non-regression
- No cloud cron changes, email sends, private GitHub ledger writes, live approval engine, new paid provider, source/keyword activation, or production branch changes.
- Gate D receives date-only support without inferring time from `00:00` or from crawl time.
- Earlier Gate B and C PRs remain independent; this branch is stacked on Gate D / Gate C.
- Prioritization, approval/audit actions, real-client configuration and Arabic visual UX remain future gates.
