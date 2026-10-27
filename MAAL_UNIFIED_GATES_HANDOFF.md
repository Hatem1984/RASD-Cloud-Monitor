# MA'AL Integration branch — Gate G1 / G2 / G3 / F
**Date:** 2026-10-27; no main merge.

## Latest verified reconciliation
- RASD production `main`: `9f6adcec3e8444bbc3eae940b8d5f62083be7551` (no local modifications).
- PR #128: draft ledger visibility hardening on main.
- PR #129: draft source/keyword audit on main.
- PR #130: draft evidence and decision contracts on PR #129.
- PR #131: draft original verified historical signal on PR #130.
- This branch `feat/maal-unified-integration-g1-20261027` is **stacked on Gate E #131**, not mergeable to main without parent review.
- G0 local `796c906` previously provided six static HTML screens, search/filter, branding and an offline Node localhost server. V0.3 `d6b6ea5` supersedes G0's static JSON with SHA-verified owner-local proof and stronger responsive/functional QA. G0 was not rewritten, discarded, or deployed.

## Gate G1 — chosen single app
- **Chosen:** `maal_web` in this integration branch, **reusing V0.3** index/html/css/js and one Python server; old G0 static server/demo-data is not used as live gateway.
- Original V0.1/V0.2/V0.3 saved as rollback in E, no deletion or rewriting.
- This branch accepts traffic **only on 127.0.0.1** (QA:52320); the V0.3 fallback stays on 52319 pending final review. Do not operate both as production applications.
- Branding references files already approved under E MAAL, no copied fonts/private images in public repository.

## Gate G2 — verified read-only local evidence API
- `/api/snapshot`: reads already-approved local RSS config, correctly reports configured (not live) status.
- `/api/case`: loads the existing historical owner-only Gate E receipt and checks exact official publisher URL/date, verifies original JPG SHA, validates Gate D `Evidence` contract and evidence identity.
- `/api/evidence`: returns an explicitly classified `HISTORICAL`, `VERIFIED_ORIGINAL_PAGE` evidence row containing source ID, published day, separate observed_at, SHA, publisher and origin URL. No private ledger, secret, mail status or production customer data.
- `/api/case-report`: downloads owner-local Word only if DOCX-embedded image hash matches original verified JPG.
- All unauthorised path requests are 404; all POSTs denied. This **does not prove a live RSS → database → customer API**; Gate G2 is PARTIAL.

## Gate G3 — AI draft adapter; NOT a live AI result
- `maal/ai_decision_engine.py` adds a `Provider` contract, strict Gate D `Evidence` validation, explicit company profile and no-action schema. Optional `LocalOllamaProvider` allows existing approved local model if ever available; never installs or starts a model.
- Local Ollama was **not installed/reachable** when checked. Tests use a fake model to prove safety contracts, **not generation quality**. Agentic reasoning, real model accuracy and counterfactual evaluation remain HOLD.
- The model receives no approval token or action-executor interface, cannot mark an approval/execution as successful, and cannot authoritatively verify publisher data.

## Gate F — separate isolated internal test action
- `maal/internal_actions.py` includes E-only independent SQLite with append-only event audit and hash chain, task deduplication, challenge-based test review, and one internal `draft_task` execution.
- Tests prove refused unauthorised/absent approvals, collision safety, exact-once inserts, failures with audit and retry, and audit immutability.
- Tests **simulate human review**. No customer or actual external action; no Gmail, GitHub, purchases, payments or scheduling changes. Production human authentication/approvals and action UI remain pending.
- Test SQLite artifacts remain only on `E:\MAAL\04_HISTORICAL_QA\MAAL_GATE_F_TEST_20261027` (not in Git).

## Gate G4 / H
- Browser still read-only and doesn't expose task execution, approval secrets or model endpoints. Owner visual experience reused without fictional approval controls.
- Integrated original-publisher → Gate D contracts → UI / rule-based proposal and separate authorised internal-task unit test pass; **full real-model E2E** remains HOLD until local/approved actual model and human approval channel exist.
- Mobile QA is Playwright viewport simulation, not physical hardware.

## Mandatory next steps
1. Close all legacy RASD regression tests and browser checks on the integration worktree, confirm one reference and rollback.
2. Verify 27 Oct production hold evidence read-only; never blind resend, touch production credentials, or scheduler.
3. When authorized model infrastructure is available, validate a **real AI run** against contradictory/insufficient evidence and ground recommendations before calling G3 complete.
4. Provide authenticated, tenant-safe staging and owner approval UX for Gate F/G4.
5. Only after sign-off, merge parent PRs sequentially; no direct main merge of stacked integration branch.

## Competition handoff
Demonstrable: historical original Ministry source proof, strict evidence identity/date SHA, V0.3 branded Arabic operator UI, and separately tested internal approval/idempotent SQLite action guard. Not demonstrable yet: real generative AI agent run, live production monitoring feed wired to UI, authenticated approval for a company, or full live competition E2E.

## Portability / non-leak policy
The 8 G3 model-boundary and 8 Gate F action tests rely on an owner-local verified historical publisher receipt and E-only test SQLite. They execute locally when that original evidence is available. Generic cloud runners without the owner proof SKIP these 16 tests explicitly, rather than fabricating proof or copying protected evidence into the public repository. The rest of the legacy/public tests remain runnable in CI. Staging acceptance must supply a separately authorized verified fixture before Gate G3/F are considered deployable.

## Confirmed acceptance on 27 Oct
- 632/632 combined RASD/MA'AL unittest suite PASS on Windows E worktree with Git Bash on PATH (before the added /api/evidence-specific HTTP assertion).
- 12/12 local UI API tests PASS including DATE-ONLY source registry classification and DOCX image SHA.
- 4 viewport sizes × 6 UI views = 24 browser screens PASS, including source modal, 6→13 toggle, clipboard memo, original Word download and navigation.
- 27 Oct production read-only GitHub Actions investigation found repeated protected HOLD statuses. No resend, scheduler edits, credentials, or recipients touched. Private owner-only runtime reconciliation remains open.
