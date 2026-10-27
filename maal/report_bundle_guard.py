"""MA'AL — immutable historical snapshot ↔ Word/PDF artifact attestation.

Provides a fail-closed association to an owner-reviewed, fixed set of bytes.
It does NOT imply new article image verification, live feeds, or that Word/PDF
dynamically regenerate whenever UI metadata changes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_MODE="HISTORICAL_LIMITED_REPORT"
EXPECTED_SCHEMA="MAAL_PRODUCT_REVIEW_V1"
EXPECTED_ARTIFACT_NAMES={
    "pdf":"MAAL_Business_Intelligence_Round2_2026-10-27.pdf",
    "docx":"MAAL_Business_Intelligence_Round2_2026-10-27.docx",
}

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def canonical_snapshot(snapshot:dict[str,Any])->bytes:
    # The timestamp/revision is deliberately separate so it cannot rewrite the
    # approved editorial facts. Even a single changed fact forces new attestation.
    raw=dict(snapshot)
    raw.pop("snapshot_meta",None)
    if raw.get("schema")!=EXPECTED_SCHEMA or raw.get("mode")!=EXPECTED_MODE:
        raise ValueError("unapproved_report_schema_or_mode")
    if raw.get("live_monitoring") is not False or raw.get("email_sent") is not False:
        raise ValueError("false_live_or_delivery_claim")
    stories=raw.get("stories")
    if not isinstance(stories,list) or len(stories)!=3:
        raise ValueError("unreviewed_story_set")
    if {s.get("id") for s in stories}!={"ministry_2026_10_17",
                                         "ministry_2026_10_24",
                                         "ministry_2026_10_26"}:
        raise ValueError("unexpected_story_identity")
    verified=[s for s in stories if s.get("verification")=="ORIGINAL_VERIFIED"]
    if len(verified)!=1 or verified[0]["id"]!="ministry_2026_10_17":
        raise ValueError("unsupported_original_image_claim")
    if any(s.get("ready_for_action") is not False for s in stories):
        raise ValueError("unreviewed_execution_claim")
    return json.dumps(raw,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False).encode("utf8")

def valid_sha(s:object)->bool:
    return isinstance(s,str) and re.fullmatch(r"[a-f0-9]{64}",s) is not None

def inspect_bundle(*,snapshot:dict[str,Any],manifest:dict[str,Any],
                   files:dict[str,bytes])->dict[str,Any]:
    if manifest.get("schema")!="MAAL_OWNER_REVIEW_BUNDLE_V1":
        raise ValueError("unknown_artifact_manifest")
    meta=snapshot.get("snapshot_meta")
    if not isinstance(meta,dict) or meta.get("kind")!="HISTORICAL_READONLY_QA":
        raise ValueError("missing_historical_snapshot_receipt")
    if meta.get("source_live_connected") is not False or meta.get("source_new_verified_news_count")!=0:
        raise ValueError("live_freshness_not_verified")
    if not isinstance(meta.get("revision"),str):
        raise ValueError("unknown_snapshot_revision")
    if manifest.get("snapshot_revision")!=meta["revision"]:
        raise ValueError("snapshot_revision_artifact_mismatch")
    snapshot_hash=digest(canonical_snapshot(snapshot))
    if not valid_sha(manifest.get("canonical_snapshot_sha256")) or snapshot_hash!=manifest["canonical_snapshot_sha256"]:
        raise ValueError("snapshot_facts_artifact_mismatch")
    parts=manifest.get("artifacts")
    if not isinstance(parts,dict) or set(parts)!=set(EXPECTED_ARTIFACT_NAMES):
        raise ValueError("incomplete_artifact_bundle")
    if set(files)!=set(EXPECTED_ARTIFACT_NAMES):
        raise ValueError("missing_artifact_bytes")
    sizes={}
    for ext,name in EXPECTED_ARTIFACT_NAMES.items():
        info=parts[ext]
        binary=files[ext]
        if (not isinstance(info,dict) or info.get("filename")!=name
            or not valid_sha(info.get("sha256")) or
            len(binary)!=info.get("size") or
            digest(binary)!=info["sha256"]):
            raise ValueError("artifact_integrity_mismatch_"+ext)
        if ext=="pdf" and not (binary.startswith(b"%PDF-") and b"%%EOF" in binary[-1024:]):
            raise ValueError("malformed_pdf")
        if ext=="docx" and not binary.startswith(b"PK\x03\x04"):
            raise ValueError("malformed_word_package")
        sizes[ext]=len(binary)
    return {
        "status":"OWNER_REVIEWED_HISTORICAL_BUNDLE_HASH_MATCH",
        "snapshot_revision":meta["revision"],
        "snapshot_sha256":snapshot_hash,
        "artifacts":{ext:{"name":parts[ext]["filename"],"bytes":sizes[ext],
                          "sha256":parts[ext]["sha256"]} for ext in sizes},
        "mode":"HISTORICAL_READ_ONLY",
        "new_verified_source_images":0,
        "live_news_verified":False,
        "email_delivery_verified":False,
        "auto_regenerated_on_revision_change":False,
    }
