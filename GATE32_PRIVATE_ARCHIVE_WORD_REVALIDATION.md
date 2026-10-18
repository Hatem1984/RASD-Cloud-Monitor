# RASD — Gate 32: independent private archive Word evidence revalidation

**Date:** 18 October 2026. **Scope:** public source code and entirely offline fake-S3 acceptance; no real private object storage, upload, key, paid subscription, Gmail, or scheduler.

## Reproduced baseline failures

After Gate 31 proved that a genuine original-publisher-page JPEG can be embedded into an accepted Word, the private S3-compatible archival boundary was separately tested with adversarial packages.

Before the fix, `PrivateEvidenceArchive.publish_ready` checked only that every expected JPEG digest **appeared somewhere** in the DOCX media and that the total count of Word inline shapes was not too small. This accepted:

1. Two individually genuine publisher JPEGs swapped between different Word articles despite the correct screenshots being supplied to the archive in the intended article order.
2. A DOCX ZIP archive containing a **duplicate media member name**, creating package-reading ambiguity.

The new offline regressions first demonstrated both failures: [red baseline](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39106176598) — 181 tests, **two expected failures**, one dependency-conditional skip. Neither case contacted real storage; fake S3 was used throughout.

## Correction

The private archive now invokes the same strict `word_images_match_capture_digests` validator as the core final Word report, **independently and before its first remote PUT**.

- Every displayed internal Word drawing must resolve to exactly its respective captured JPEG SHA-256 **in article order**.
- Duplicate OPC/ZIP parts, unused media, reused picture targets, altered JPEGs and external image relations remain invalid.
- An invalid Word yields `private_archive_embedded_screenshot_mismatch` and **zero objects uploaded**.
- Existing content-addressed immutable object writes, SHA-256 full GET readback, archive budgets and last-write commit manifest remain unchanged.

## Explicitly not accepted

This test does **not** prove real R2 or S3 access, paid/free-tier eligibility, bucket privacy, encryption key custody, retention, restore drill, Gmail or daily scheduling. Those require separately approved owner-managed protected infrastructure, followed by a real private restore acceptance. Gate 31's single live 1/1 article Word success was an ephemeral runner proof, not a production archival event.
