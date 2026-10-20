# Gate71 — R2 private backup readiness for owner CIPHERTEXT only

20 October 2026. Gate71 is **offline engineering** and not remote R2 acceptance, storage provisioning or a change of publisher source and keywords.

This module prepares an immutable original owner ciphertext object identity for **`RASD_G43_OWNER_ENCRYPTED`** RSA/AES-GCM JSON with precisely four outer keys (`format`, `wrapped`, `nonce`, `ciphertext`), strict bounded base64 decoding and shape checks. It **rejects plaintext Word, publisher PNG/JPEG, arbitrary extra JSON fields, manipulated/enlarged envelopes, today's partial Cairo date and invalid source identity**. The object key includes completed Cairo day and SHA-256 of the **raw encrypted JSON bytes**, never article names or an email address.

A local synthetic bytes round-trip proves that a same-date backup plan points to the identical encrypted payload; swapping a valid but different encrypted envelope returns HOLD. The code intentionally does not use AWS/Boto3, S3/R2 access, any bucket or secret, HTTP, Gmail, or the owner's RSA private key. The only permitted result labels are `ENCRYPTED_OWNER_R2_NO_NETWORK_PREFLIGHT_ONLY` and `LOCAL_CIPHERTEXT_BYTES_ROUNDTRIP_ONLY`; neither implies an actual object upload/remote read-back or that AES-GCM has been authenticated.

**Already retained real owner evidence:** owner ciphertext for 2026-10-17 and 2026-10-19 is in separate original encrypted packages and a consolidated local ZIP, no private key or decrypted Word uploaded. Genuine interactive owner Gate61 visual review of BOTH real report dates and Gate62 two-day acceptance is still pending.

**To finish R2 Stage4 in future (not approved in this gate):** choose and authorize a private bucket, minimum-scope S3 credentials in protected environment only, versioning/object immutability or collision-safe idempotent key, encrypted-object-only upload with SHA receipt, independent remote GET comparing exact ciphertext byte SHA and an actual owner-local private-key decrypt/review, one retention policy with recovery trial, cost/quotas and deleted-object recovery controls. Never upload an unencrypted Word, per-article JPEG or owner's private RSA key. No new paid hosting, cloud account provisioning, bucket, new workflow schedule or production storage is activated here.

This is not a substitute for real R2 access approval or a full restore exercise. Existing R2 Issue #35 remains HOLD.
