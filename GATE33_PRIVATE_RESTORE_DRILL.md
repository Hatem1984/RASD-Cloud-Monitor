# RASD — Gate 33: private evidence restore drill (offline only)

**Date:** 18 October 2026  
**Status:** Isolated code acceptance in memory-backed Fake-S3; **NOT** actual Cloudflare R2 production restore.

## What is implemented

`private_evidence_restore.restore_verified_bundle` is a read-only, in-process restore verifier for an already authorized `PrivateEvidenceArchive` client. It creates **no** cloud account, bucket, credentials, public endpoint or scheduled workflow. The caller supplies a private manifest key and its expected SHA-256.

Verification is performed in this order:

1. Reject path traversal, unapproved prefixes, malformed dates and manifest-key/hash mismatch **before any request**.
2. Obtain a bounded private manifest; compare the full bytes to the independent expected SHA-256.
3. Require the exact versioned manifest schema, READY status, 1–15 article entries, unique valid article IDs, correct content-addressed paths and total byte budget.
4. Fetch the original private Word and every JPEG using bounded full GET reads; verify byte count, SHA-256, JPEG signature, and absence of missing objects.
5. Independently validate the **restored** DOCX drawing relationships against the restored article-JPEG digests in exact article order, using the Gate 27–29 evidence verifier.
6. Return only non-sensitive verification metadata by default; validated private Word/JPEG bytes are returned in-process **only** when the trusted caller explicitly requests `include_bytes=True`.

The implementation does **not** write any recovered file to a public artifact or log. The temporary Word used for OPC verification is deleted after the check.

## Evidence

Five new offline tests using Fake-S3 establish:
- successful full restore with byte-for-byte equality to the originally submitted Word and JPEG;
- a metadata-only safe default;
- fail-closed on an altered manifest, altered Word object or missing JPEG;
- fail-closed on unexpected manifest path or forged content-addressed manifest pointing outside the RASD namespace.

The tests never reach Cloudflare or another paid service. Offline CI: [GitHub Actions run 39106564870](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39106564870).

## What remains open

This is **not** a production storage acceptance. It has not verified real bucket permissions, customer-managed encryption/key recovery, object-store availability, retention, storage costs, real R2 read-back/restore or authenticated API authorization. Those require a separately approved private environment and deliberate one-run live acceptance. Gmail, scheduling and automated delivery remain OFF.
