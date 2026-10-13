# RASD Cloud Monitor — Public News Worker (staging)

A standalone, **public-source-only** monitoring worker for Egyptian Ministry of Planning news. This repository is intentionally independent from the private RASD platform and from the earlier public browser-proof repository.

## Current status

**STAGING — MANUAL DRY-RUN ONLY.** GitHub Actions has no `schedule` trigger. This repository cannot send email, publish a report or persist news state across runs. Do not claim production readiness.

## What is implemented

- Restricted HTTPS RSS intake from the verified native Hapi publisher feed, with strict direct-publisher link checks
- Ministry of Planning keyword matching, recency filtering and within-run URL deduplication using public-article fingerprints
- Safe bounded XML responses, redirect refusal and denial of DTD/entity declarations
- Explicit outage reporting, including fail-closed behavior when all configured feeds fail
- Offline standard-library tests and a manual GitHub Actions acceptance test with a one-day artifact
- No Gmail credentials, email address, secret files, private article lists or private RASD files

## What is deliberately **not** enabled

- Scheduled 15–30-minute monitoring
- Persistent cross-run deduplication, exactly-once delivery and private state storage
- Screenshots and image quality verification (already separately proved in a different test repository)
- Gmail notifications, Word/PDF generation and report delivery
- Other publishers such as Youm7: the tested RSS endpoint failed standard XML parsing on GitHub, so it is not trusted yet

## Safety and cost constraints

1. Only content already published on public websites may enter this public repository. Never upload private RASD source, internal records, user names, credentials, contact information, Gmail tokens or generated personal reports.
2. The GitHub Actions workflow has `permissions: contents: read`, no cron and no secret access. It only reads one fixed public feed.
3. Public GitHub Actions runner costs are subject to GitHub's current free-tier and account rules. Verify account billing settings before enabling recurrence. Never increase a billing limit or add a payment method without explicit owner consent.
4. No files are installed or saved on the owner's computer or OneDrive by this process.

## Manual test

Open **Actions → RASD public monitoring — manual dry-run only → Run workflow**.

The workflow runs `python -m unittest discover -s tests -v` and `python monitor.py`. It generates `evidence/latest-probe.json`, with counts, reviewed publisher headline matches and *no* user data. An empty match set is a valid result and does **not** establish full media coverage.

## Next acceptance gates

- Test this repository's manual workflow once and review the GitHub run and artifact
- Implement durable state and run-to-run dedupe with a no-private-data approach
- Separate public capture from private delivery (no email credentials or addresses in Git history)
- Prove end-to-end delivery **before** introducing a production schedule

This repository is an **execution scaffold**, not a deployed autonomous media service.
