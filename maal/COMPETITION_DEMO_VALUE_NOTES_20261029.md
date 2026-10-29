# MA'AL | Competition judge briefing & value protocol (working notes)

**Status:** Internal working notes, NOT a submitted pitch deck, published demonstration, new owner approval or measured ROI. **29 Oct 2026**. The current owner-held Pitch Deck is on a private Windows E: directory, so its latest binary content has **not** been independently opened in this recovery session. Preserve it; reconcile text after local access.

## Judge-facing 90-second English narration (truthful version)

> Small businesses face a difficult decision every day: Which market, technology or regulatory developments actually matter to them? Headlines alone don't answer that question. MA'AL is designed to connect independently captured publisher evidence with a specific company's profile, then distinguish verified facts, potential business consequences, missing conditions, alternatives and a proposed internal follow-up. Unlike a news summarizer, it has a bounded workflow for verification, business relevance, review, owner decision and auditable internal action. The owner—not the model—decides whether a task is approved. We currently have a private local prototype and an independently verified historical workflow, while the newest two-stage reasoning approach remains under real-model testing. We won't claim measurable savings or a new end-to-end approved decision until those tests are finished. Our goal is to give smaller teams better-grounded decisions with traceable evidence and human control.

## Screens for an honest short demo

1. **Scope banner:** Private localhost prototype, historical captured evidence. Not a live market feed.
2. **Source:** Publisher name, original URL, publication day **separate** from page capture time, JPEG and SHA-256.
3. **Business relevance:** Registered synthetic Egyptian digital studio; no assumed existing FPT partnership, EU customer, subsidy or revenue.
4. **AI outcome:** New Stage 1 output and evidence-linked run ID, with real inference duration. On-screen label must say *replayed saved run* if not recorded while the inference is actually happening.
5. **Action contract:** Show Stage 2 only when Stage 1 was valid and ACTION_WORTH_REVIEW. Otherwise show justified abstention/HOLD, no implied action.
6. **Human review:** Current state (not editorially accepted unless an owner independently signs the actual response).
7. **Owner decision & audit:** Only show a newly approved/executed task after real owner approval and one authorized internal execution. Otherwise explicitly stop at pending human approval.
8. **Competition materials:** Existing Word/PDF and older demo can illustrate history, not future features.

## Evidence table for judge selection

| Scenario | Evidence source | Relevance question | Critical unsupported leap to avoid |
|---|---|---|---|
| FPT | Publisher original capture, SHA-256 pinned on E: | Could a local digital studio face competitive hiring or service pressure? | FPT is a partner/customer or immediate direct competitor |
| ITIDA | Publisher original capture, SHA-256 pinned on E: | Are the announced skills opportunities actually available to this studio or only selected trainees? | A trainee programme is a grant or guaranteed corporate contract |
| European Commission | EU publisher original capture, SHA-256 pinned on E: | Does the relevant regulation apply to the Egyptian studio's services and customers? | EU AI Act automatically applies to all Egyptian companies |

The exact evidence IDs, original URL receipts and hashes must be loaded from the **real verified_cases()** validator and local model receipts; do not type them into slide visuals from memory.

## Frozen human business-value comparison — one real participant

**One synthetic company:** an Egyptian SME providing digital-product creation and basic AI training, with no confirmed sales or international operations.

**One assignment, same sources:** "Assess FPT's announced Egypt expansion. Should the company take a small internal next step? Justify your answer and identify uncertainty."

**Manual path:** Participant starts their own timer *before* opening the published source. They gather, check quote accuracy, assess business fit, write a proposed action or abstention, then stop the timer. Save the actual duration, source URL and response.

**MA'AL path:** Start a separate timer *before* opening MA'AL. Include reviewing publisher image/hash, AI results, assumptions, accepting or rejecting the recommendation, drafting the participant's own decision and stop the timer. Cached model results must be disclosed; do not treat API load latency alone as the full task duration.

**Score without changing thresholds:** an independent reviewer compares the same five dimensions for each path: exact source fidelity, correct beneficiary, causal validity, decision/abstention usefulness, and executable internal deliverable. Record number of critical errors and disagreements. Source links, times and reviewer notes must be preserved in the existing business-value-study tool. No percentage gain, financial ROI or statistical confidence is claimed for one participant.

## Release gates before judge-ready status

- Four-width browser QA + owner session/decline/blocked approval.
- Explicit keyboard walkthrough and screen-reader operator observation; automated checks alone are not WCAG 2.2 AA certification.
- Three **fresh** Qwen3-1.7B Stage 1 executions on original source captures, and conditional Stage 2, with independent semantic editorial assessments.
- Independent human review of at least one specific recommended task; a new owner DRAFT only after review and evidence/run hashes align.
- No owner approval without owner step-up. No email, financial or external actions.
- One participant's manual-vs-agent business value trial and transparent summary.
- Final visual signoff, presentation verification and explicit submission permission.

**Current official competition information:** https://www.dubaichambers.com/en/web/dubai-chamber-of-digital-economy/create-ai-agents — early MVP/prototype permissible, materials in English, January 2027 submission phase. The site does not supply a verified mandatory demo length or pitch-slide count here. An official earlier announcement gave a differing registration-close period; check the participant portal before final scheduling. No submission made here.
