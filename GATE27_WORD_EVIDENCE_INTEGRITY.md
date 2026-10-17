# RASD — Gate 27: final Word screenshot integrity

**Date:** 17 October 2026  
**Scope:** Cloud-only public-source Word evidence integrity; no Gmail, cron, paid storage, Windows dependency, new publisher access, or production authorization.

## Engineering change

The base `cloud_proof_report.build_proof_report` now validates its **actual Word document**, not just screenshot receipt counters or picture counts. For every verified article:

- A legitimate original-publisher JPEG must have been captured under the existing provenance and visual-quality checks.
- The exact screenshot SHA-256 from that capture must equal the bytes of one image displayed by a Word drawing, as resolved through the DOCX drawing/relationship mapping.
- Unused/orphan media, reused media masquerading as different articles, missing evidence pictures, mutated bytes, bad ZIP integrity, external image relationships, or digest disagreement fail the final report.
- A failure produces `HOLD` and **no final Word**, and cannot reach the optional private archive writer. The previous same-day scratch Word is removed before each attempt so a failing retry does not expose a misleading old final document.
- No historical image, fake screenshot, publisher-access bypass, or guessed news story is accepted as a substitute.

The Gate26 Shorouk-only acceptance and its encrypted owner review artifacts remain separate; this Gate27 rule now covers the **core** report builder used by the manual Gmail digest as well.

## Tested acceptance

- Cloud run [39069309452](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39069309452): **BOTH** the offline-security job and the real-public-feed read-only job PASSED on branch `gate27-word-evidence-integrity` at SHA `bef9801ca8ddff79bd1c5a407e982d0137b946f7`.
- **175 offline unit tests** completed successfully, with one conditional crypto-runtime skip in the dependency-minimal job. The separate dedicated encryption workflow covers cryptographic artifact tests.
- New negative regressions cover tampered JPEG in DOCX, omitted picture, orphan media part, same-day failed retry, and two individually distinct mocked original publisher images. The fixtures are synthetic **only for offline QA**, never delivered or attributed to a real publisher.
- The public RSS read-only CI remained green. That success does **not** assert a new eligible live article, successful full-source screenshots, real private archiving, Gmail SMTP delivery, or an automatic scheduler.

## Remaining production hold points

1. Reviewed full multi-publisher capture and evidence completeness; temporary source failures remain `HOLD`.
2. Owner-protected private cloud storage, credentials, retention/restore, and SHA-256 read-back in production.
3. Actual GitHub protected environment, Gmail authentication-only preflight, separately approved real email, private ledger receipt, and Gmail Sent/Inbox reconciliation.
4. Owner-approved scheduling, retries, monitoring and incident notifications.
5. Authenticated API and Android/Windows applications if the complete originally proposed product is in scope.

**Operational release policy:** do not label the product production-ready merely because this gate's tests pass. Mail and scheduling stay disabled until separate consent and live acceptance.
