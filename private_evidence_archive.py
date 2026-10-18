"""Cloud-only private RASD evidence archive: S3-compatible, R2-ready.

No bucket is created, no public URLs are generated and no network is used
unless a separate owner-approved publisher explicitly supplies an S3 client.
This is not a screenshot bypass and never reads SMTP or private Gmail state.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from cloud_proof_report import word_images_match_capture_digests

MAX_FILE_BYTES = 50_000_000
MAX_SCREENSHOT_BYTES = 8_000_000
MAX_BATCH_BYTES = 75_000_000  # Budget guardrail: images + Word for ONE run
_HEX_ID = re.compile(r"^[0-9a-f]{24}$")
_HEX_SHA = re.compile(r"^[0-9a-f]{64}$")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes_from_file(path: Path) -> bytes:
    size = path.stat().st_size
    if not 8000 <= size <= MAX_FILE_BYTES:
        raise ValueError("evidence_archive_file_size_invalid")
    return path.read_bytes()


class PrivateEvidenceArchive:
    """Store immutable content-addressed JPEG/DOCX; verify server readback.

    HEAD metadata by itself is insufficient: GET and SHA256 are checked.
    The manifest is the LAST object and signals a fully verified archive.
    """

    def __init__(self, s3_client, *, bucket: str, prefix: str = "rasd/v1"):
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
            raise ValueError("invalid_private_bucket_name")
        if prefix != "rasd/v1":
            raise ValueError("unapproved_evidence_key_prefix")
        self.client = s3_client
        self.bucket = bucket
        self.prefix = prefix

    def put_verified(self, key: str, data: bytes, content_type: str) -> dict:
        if not key.startswith(self.prefix + "/") or ".." in key:
            raise ValueError("invalid_private_evidence_key")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("private_object_too_large")
        digest = _sha(data)
        # Immutable naming ensures that a changed byte creates a new path.
        # Conditional create prevents a retry from overwriting old evidence.
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=data,
                ContentType=content_type, Metadata={"sha256": digest},
                IfNoneMatch="*",
            )
        except Exception as exc:
            # Only precondition conflicts are tolerable for idempotent retries.
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code not in ("PreconditionFailed", "412"):
                raise
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        content_length = response.get("ContentLength")
        if content_length != len(data):
            raise RuntimeError("private_evidence_size_readback_mismatch")
        actual = response["Body"].read(len(data) + 1)
        if len(actual) != len(data) or _sha(actual) != digest:
            raise RuntimeError("private_evidence_digest_readback_mismatch")
        return {"key": key, "sha256": digest, "bytes": len(data)}

    def publish_ready(self, *, report: dict, word: Path,
                      evidence: list[tuple[str, Path, str]]) -> dict:
        if report.get("status") != "READY" or report.get("coverage") != "HEALTHY":
            raise RuntimeError("private_archive_requires_complete_report")
        if not report.get("word_created") or report.get("screenshots_missing") != 0:
            raise RuntimeError("private_archive_requires_complete_evidence")
        count = report.get("articles")
        if type(count) is not int or not 1 <= count <= 15 or len(evidence) != count:
            raise RuntimeError("private_archive_evidence_count_mismatch")
        name = word.name
        m = re.fullmatch(r"RASD-Daily-(\d{4}-\d{2}-\d{2})\.docx", name)
        if not m:
            raise ValueError("private_archive_word_name_invalid")
        day = date.fromisoformat(m.group(1)).isoformat()
        # Preflight ALL local evidence before the first remote PUT.
        # An invalid last screenshot must not leave billable, orphaned
        # objects from the earlier articles.
        unique = set()
        staged = []
        total_bytes = 0
        for article_id, image, declared_sha in evidence:
            if (not _HEX_ID.fullmatch(article_id) or article_id in unique or
                    not _HEX_SHA.fullmatch(declared_sha)):
                raise ValueError("invalid_archive_article_proof")
            unique.add(article_id)
            payload = _bytes_from_file(image)
            if len(payload) > MAX_SCREENSHOT_BYTES:
                raise ValueError("private_screenshot_too_large")
            if not payload.startswith(b"\xff\xd8") or _sha(payload) != declared_sha:
                raise RuntimeError("private_archive_screenshot_mismatch")
            total_bytes += len(payload)
            staged.append((article_id, declared_sha, payload))

        word_bytes = _bytes_from_file(word)
        if not word_bytes.startswith(b"PK"):
            raise RuntimeError("private_archive_word_format_invalid")
        total_bytes += len(word_bytes)
        if total_bytes > MAX_BATCH_BYTES:
            raise ValueError("private_archive_batch_budget_exceeded")
        # Revalidate at the independent PRIVATE storage boundary, even if
        # the caller already accepted this Word. A digest SET comparison
        # would accept genuine JPEGs swapped between different articles.
        # Resolve every displayed DOCX image relationship and enforce the
        # exact ordered publisher capture digests; also reject duplicate ZIP
        # member names, orphan parts and external image relationships.
        receipts = [{"status": "verified", "sha256": digest}
                    for _, digest, _ in staged]
        if not word_images_match_capture_digests(word, receipts):
            raise RuntimeError("private_archive_embedded_screenshot_mismatch")

        # Only now is remote storage allowed. The commit marker still
        # uploads last, and every object is checked by a full GET readback.
        outputs = []
        for article_id, digest, payload in staged:
            key = f"{self.prefix}/{day}/screenshots/{article_id}-{digest}.jpg"
            outputs.append({"article_id": article_id,
                            **self.put_verified(key, payload, "image/jpeg")})
        word_hash = _sha(word_bytes)
        word_key = f"{self.prefix}/{day}/reports/{word_hash}.docx"
        word_ref = self.put_verified(
            word_key, word_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        manifest = {
            "schema_version": 1, "date_cairo": day, "status": "READY",
            "articles": count, "screenshots": outputs, "word": word_ref,
        }
        # Commit marker is LAST: missing marker means archive is incomplete.
        manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":"))
                          + "\n").encode("utf-8")
        manifest_hash = _sha(manifest_bytes)
        manifest_key = f"{self.prefix}/{day}/manifests/{manifest_hash}.json"
        marker = self.put_verified(manifest_key, manifest_bytes, "application/json")
        return {"status": "PRIVATE_VERIFIED",
                "manifest_key": marker["key"],
                "manifest_sha256": marker["sha256"],
                "screenshots_archived": count,
                "word_archived": True, "bytes_checked": total_bytes}
