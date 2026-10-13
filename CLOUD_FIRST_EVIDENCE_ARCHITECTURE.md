> **Superseding decision — 14 October 2026, Gate 19:** RASD outputs **Word (.docx) only**. PDF generation, PDF attachments and PDF uploads are retired. RSS-only Word files are explicitly named `RASD-Preview-YYYY-MM-DD.docx` and are NOT final reports. A final `RASD-Daily-YYYY-MM-DD.docx` is produced only after all included news items have validated screenshots of their original publisher webpages and coverage is healthy; otherwise the report is `HOLD`. The protected email workflow is manual-only and must not send incomplete reports. Content below includes historical pre-Gate19 acceptance notes for audit continuity.

# RASD — Cloud-first publisher evidence architecture

**Decision (14 October 2026):** RASD is a cloud service, not a Windows-PC automation. The later Android APK and Windows EXE are authenticated clients for the SAME central API.

## Non-negotiable report acceptance

- Every item in a *final evidenced report* must include an actual screenshot of its own original publisher article page, the original URL, headline, publisher and publication time.
- A stock photo, original article thumbnail, synthetic page, historical reference, browser challenge screen or screenshot of a different story must NEVER replace that evidence.
- A source refusal (HTTP 401/403), deletion (404/410), rate limit (429), publisher downtime (5xx), failed visual QA or inconsistent title/URL gives `HOLD`, never `READY`. Preserve pending article metadata for a retry governed by publisher access policy.
- Do not evade publisher access restrictions or access-controlled content. Respect source terms, permitted use, robots directives and licensing. Where required, obtain an authorized publisher feed/API or agreement.
- The older `daily_report.py` is a **text-only preview**, not a final screenshot-compliant report. The new `cloud_proof_report.py` is the strict evidence gate. Do not treat the existing email pipelines as screenshot-proof daily reports.

## Cloud components (planned production design)

```text
Original publisher RSS / authorized feeds
            |
     News Ingestion API (validate, deduplicate and timestamp)
            |
       Database + Job Queue
            |
   Cloud Playwright Capture Worker
   [validated publisher URL + page screenshot + SHA-256]
            |
   Private/Object Evidence Storage + per-item audit state
            |
   Report Composer (Word/PDF; ALL items require proof)
            |
     Central RASD API (auth, audit, reports, queues)
          /   |   \
     Web admin  Android APK   Windows EXE
```

The operator's computer can be powered off. All jobs run on hosted infrastructure. Only the API handles authentication, retrieval, device access and permissions; clients never hold SMTP or publisher-access credentials.

### Working staging implementation

- Existing GitHub-hosted RSS read and browser capture can already run without the owner's PC.
- Gate18 adds `cloud_proof_report.py` and evidence embedding in existing Arabic Word/PDF renderers. This path is manual and deliberately fails closed when screenshots are incomplete.
- The QA branch tests use synthetic images *only for regression tests*, not production evidence.
- Current GitHub run artifacts last one day and the code repository is public; do not use public Actions artifacts as a permanent copyright-sensitive screenshot database.

### Production hosting option

A **Dockerized Python/Playwright worker** plus API can run on Railway or another authorized cloud/VPS host. Railway currently documents Playwright Docker deployments and separate long-running/cron services. Configuration and expenditure require separate approval; no deployment, paid service or cron has been enabled by this design.

Plan database records: `sources`, `articles`, `capture_attempts`, `evidence`, `report_jobs`, `reports`, `app_users`, `audit_events`. Object storage keeps screenshots and generated docs privately with signed access URLs. A job queue gives bounded retries with backoff for transient 429/5xx; permanently denied 401/403 stays pending authorization. Report status is `READY` only if every included article is screenshot-verified; `HOLD` and a reason are visible in both clients.

### APK and EXE design

Android and Windows clients share login, dashboards, article details, screenshot preview, report history and approved Word/PDF downloads from the same API. Neither hosts the monitor nor requires the owner's laptop to remain on. Offline clients may display previously cached authorized results, clearly dated; server processes never depend on the client session.

### Security and rights

Use egress allowlists, reject redirects away from publisher, inspect downloaded binary, enforce source/title match, validate SHA-256, apply per-source budgets and request rates, and avoid public secret logging. Separate publicly published headlines from screenshot media retention rights; legal/publisher approval may be needed to capture, retain and distribute copyrighted page screenshots. Do not use proxy rotation or browser fingerprint spoofing to circumvent publisher blocks.

### Gates still required

1. Complete full mocked cloud proof report tests and deploy a **manual non-email worker** for controlled staging.
2. Confirm a real original-publisher screenshot for **every** selected item on the chosen service; obtain authorized access or adjust approved sources when a publisher denies bots.
3. Provision private object storage and a durable DB; validate retention, per-user access and event log.
4. Deploy authenticated API, then build APK/EXE thin clients against that API.
5. Approve real Gmail preflight, sending and scheduled cloud jobs separately.
