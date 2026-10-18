"""Read-only, fail-closed private RASD evidence recovery verification.

This module creates no S3 client, downloads no public URLs, writes no permanent
files and is not connected to an Actions workflow or an HTTP endpoint.
Caller must already have an authorized private archive client. Recovered
publisher images / Word bytes must NEVER be logged or publicly uploaded.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import date
from pathlib import Path

from cloud_proof_report import word_images_match_capture_digests
from private_evidence_archive import (
    MAX_BATCH_BYTES, MAX_FILE_BYTES, MAX_SCREENSHOT_BYTES, PrivateEvidenceArchive,
)

_MAX_MANIFEST_BYTES = 200_000
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[0-9a-f]{24}$")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _get_verified(archive: PrivateEvidenceArchive, *, key: str,
                  expected_sha: str, length: int, limit: int) -> bytes:
    if (type(length) is not int or not 1 <= length <= limit or
            not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha)):
        raise RuntimeError("private_restore_invalid_object_descriptor")
    try:
        response = archive.client.get_object(Bucket=archive.bucket, Key=key)
        actual_length = response.get("ContentLength")
        if actual_length != length:
            raise RuntimeError("private_restore_object_length_mismatch")
        raw = response["Body"].read(length + 1)
    except RuntimeError:
        raise
    except Exception:
        # Never disclose private bucket/object details in a public log.
        raise RuntimeError("private_restore_object_unavailable") from None
    if len(raw) != length or _digest(raw) != expected_sha:
        raise RuntimeError("private_restore_object_digest_mismatch")
    return raw


def restore_verified_bundle(archive: PrivateEvidenceArchive, *,
                            manifest_key: str, expected_manifest_sha256: str,
                            include_bytes: bool = False) -> dict:
    """Verify a complete private manifest + exact Word/JPEG archive read-back.

    Fail closed on malformed keys, incomplete manifests, missing/corrupt
    objects, budget excess and images attached to the wrong Word articles.
    By default return only sanitized metadata; explicit include_bytes=True
    exposes validated private bytes to the authorized in-process caller.
    """
    if type(include_bytes) is not bool or not isinstance(manifest_key, str):
        raise RuntimeError("private_restore_invalid_request")
    prefix = re.escape(archive.prefix)
    found = re.fullmatch(
        rf"{prefix}/(\d{{4}}-\d{{2}}-\d{{2}})/manifests/([0-9a-f]{{64}})\.json",
        manifest_key,
    )
    if (not found or not isinstance(expected_manifest_sha256, str) or
            not _SHA.fullmatch(expected_manifest_sha256) or
            found.group(2) != expected_manifest_sha256):
        raise RuntimeError("private_restore_manifest_identity_mismatch")
    try:
        day = date.fromisoformat(found.group(1)).isoformat()
        if day != found.group(1):
            raise ValueError("noncanonical date")
    except ValueError:
        raise RuntimeError("private_restore_manifest_identity_mismatch") from None

    # Bounded, digest-verified manifest is the archive commit marker.
    try:
        response = archive.client.get_object(Bucket=archive.bucket, Key=manifest_key)
        size = response.get("ContentLength")
        if type(size) is not int or not 1 <= size <= _MAX_MANIFEST_BYTES:
            raise RuntimeError("private_restore_invalid_manifest_size")
        manifest_raw = response["Body"].read(size + 1)
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("private_restore_manifest_unavailable") from None
    if len(manifest_raw) != size or _digest(manifest_raw) != expected_manifest_sha256:
        raise RuntimeError("private_restore_manifest_digest_mismatch")
    try:
        manifest = json.loads(manifest_raw)
        if (type(manifest) is not dict or set(manifest) != {
            "schema_version", "date_cairo", "status", "articles",
            "screenshots", "word",
        }):
            raise ValueError()
        count = manifest["articles"]
        if (type(manifest["schema_version"]) is not int or
                manifest["schema_version"] != 1 or
                manifest["date_cairo"] != day or manifest["status"] != "READY" or
                type(count) is not int or not 1 <= count <= 15 or
                type(manifest["screenshots"]) is not list or
                len(manifest["screenshots"]) != count or
                type(manifest["word"]) is not dict):
            raise ValueError()
        word_ref = manifest["word"]
        if set(word_ref) != {"key", "sha256", "bytes"}:
            raise ValueError()
        word_sha = word_ref["sha256"]
        if not isinstance(word_sha, str) or not _SHA.fullmatch(word_sha):
            raise ValueError()
        if word_ref["key"] != f"{archive.prefix}/{day}/reports/{word_sha}.docx":
            raise ValueError()
        if (type(word_ref["bytes"]) is not int or
                not 8000 <= word_ref["bytes"] <= MAX_FILE_BYTES):
            raise ValueError()
        total = word_ref["bytes"]
        seen = set()
        for row in manifest["screenshots"]:
            if type(row) is not dict or set(row) != {
                "article_id", "key", "sha256", "bytes",
            }:
                raise ValueError()
            article_id, shot_sha = row["article_id"], row["sha256"]
            if (not isinstance(article_id, str) or not _ID.fullmatch(article_id) or
                    article_id in seen or not isinstance(shot_sha, str) or
                    not _SHA.fullmatch(shot_sha)):
                raise ValueError()
            seen.add(article_id)
            if row["key"] != (
                    f"{archive.prefix}/{day}/screenshots/{article_id}-{shot_sha}.jpg"):
                raise ValueError()
            if (type(row["bytes"]) is not int or
                    not 8000 <= row["bytes"] <= MAX_SCREENSHOT_BYTES):
                raise ValueError()
            total += row["bytes"]
        if total > MAX_BATCH_BYTES:
            raise ValueError()
    except (TypeError, ValueError, KeyError):
        raise RuntimeError("private_restore_invalid_manifest") from None

    # No writes to remote storage. Full GET + digest on ALL referenced objects.
    word = _get_verified(archive, key=word_ref["key"],
                         expected_sha=word_sha, length=word_ref["bytes"],
                         limit=MAX_FILE_BYTES)
    screenshots = []
    for row in manifest["screenshots"]:
        image = _get_verified(archive, key=row["key"],
                              expected_sha=row["sha256"], length=row["bytes"],
                              limit=MAX_SCREENSHOT_BYTES)
        if not image.startswith(b"\xff\xd8"):
            raise RuntimeError("private_restore_invalid_jpeg")
        screenshots.append((row["article_id"], row["sha256"], image))

    # Re-apply the exact final Word per-article image validator to the
    # RESTORED bytes, not just archive metadata or an object-store HEAD.
    with tempfile.TemporaryDirectory(prefix="rasd-private-restore-") as directory:
        path = Path(directory) / "restored.docx"
        path.write_bytes(word)
        receipts = [{"status": "verified", "sha256": digest}
                    for _, digest, _ in screenshots]
        if not word_images_match_capture_digests(path, receipts):
            raise RuntimeError("private_restore_word_image_binding_mismatch")

    result = {
        "status": "PRIVATE_RESTORE_VERIFIED", "articles": count,
        "date_cairo": day, "manifest_sha256": expected_manifest_sha256,
        "word_sha256": word_sha, "screenshots_verified": len(screenshots),
        "bytes_checked": total,
    }
    if include_bytes:
        result["word_bytes"] = word
        result["screenshots"] = [
            {"article_id": key, "sha256": digest, "jpeg_bytes": raw}
            for key, digest, raw in screenshots
        ]
    return result
