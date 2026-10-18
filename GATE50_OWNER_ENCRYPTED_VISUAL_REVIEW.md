# RASD Gate 50 — Owner-only visual review of actual Word pages

**Scope:** Ministry of Planning source originals, two native RSS feeds, original exact four saved ministry search phrases; **not** generic economic news.

## Objective

The previous owner-encrypted Word was authentic, but each rendered page was destroyed immediately after the machine visual preflight. That forced the owner to independently render Word before inspecting page breaks/Arabic shaping. Gate 50 now packs the **fully machine-validated 1600px rendered PNGs of the Word pages** inside the **same RSA-OAEP/AES-GCM owner-only ciphertext**. Original Word/JPEG SHA binding remains unchanged. The temporary conversion PDF remains ephemeral and is NOT packaged or delivered (Word remains the original report format).

## Verified implementation

- The existing `rendered_word_preflight` keeps strict original publisher source image width >=3 inches, Arabic headline survival in PDF text layer, max page count, blank/solid page rejection and source-screenshot image count. Only after all checks pass are actual Word page rasters staged for the encrypted owner package. 1600px size serves legibility when images are explicitly staged for owner review; ordinary machine-only checks remain lighter 950px.
- `pack_owner_review` requires READY_QA_ONLY + all source and image proof + passing renderer before bundling the original Word. New optional `review_pages_dir` is validated for sequential page-001.png etc, genuine PNG signature, size/dimensions, total byte bounds, no symlinks, consistent page count. It embeds a SHA-256 page manifest and the image bytes **only within ciphertext**.
- Owner local `unpack_owner_review` verifies zip member allowlisting, archive byte limits, unique names and the manifest's SHA-256 values BEFORE writing decrypted Word/page files into the chosen local folder.
- Source outage or image HOLD => encrypted **audit-only** artifact; no Word, rendered PNG or PDF. No private RSA key or plaintext media sent to GitHub public Actions.
- Human review flag remains FALSE until the owner/authorized human actually opens and inspects each page. Machine decrypt-and-hash validation is NOT a human signoff.

## CI validation vs Stage 2 release

The added branch-only synthetic Word→actual LibreOffice PDF/PNG→private AES/RSA encrypted bundle→local decrypt→SHA comparison workflow tests mechanics with an ephemeral synthetic RSA pair. It does **not** prove any new live original publisher Word or a human's visual review.

**Still open for Stage 2 100%:** owner explicitly reviews authentic decrypted Word and pages, and another distinct COMPLETE Cairo day has a real qualifying Word with all three sources healthy. The known Oct17 original Word remains earlier evidence, but earlier ciphertext artifacts are not modified by this change and do not retroactively contain page rasters. Last observed real Ministry-source run on 18 Oct returned HOLD because native Al Masry Al Youm RSS was malformed on that attempt. Full unapproved delivery and the next steps — R2/private storage, Gmail, scheduler — remain OFF.
