"""Portable artifact-integrity tests; no owner Word/PDF bytes committed to GitHub."""
from __future__ import annotations
import copy
import hashlib
import json
import unittest
from pathlib import Path

from maal.report_bundle_guard import (
    canonical_snapshot,digest,inspect_bundle,EXPECTED_ARTIFACT_NAMES
)

HERE=Path(__file__).resolve().parents[1]
DATA=json.loads((HERE/"maal_web"/"product_report.json").read_text("utf8"))

class BundleGuardTests(unittest.TestCase):
    def setUp(self):
        self.snapshot=copy.deepcopy(DATA)
        self.snapshot["snapshot_meta"]={
            "revision":"stable-review-1",
            "kind":"HISTORICAL_READONLY_QA",
            "source_live_connected":False,
            "source_new_verified_news_count":0,
        }
        self.files={
            "pdf":b"%PDF-1.7\n% Test fixture only\n%%EOF",
            "docx":b"PK\x03\x04synthetic-test-only",
        }
        self.manifest={
            "schema":"MAAL_OWNER_REVIEW_BUNDLE_V1",
            "snapshot_revision":"stable-review-1",
            "canonical_snapshot_sha256":digest(canonical_snapshot(self.snapshot)),
            "artifacts":{
                ext:{"filename":EXPECTED_ARTIFACT_NAMES[ext],
                     "size":len(b),"sha256":digest(b)}
                for ext,b in self.files.items()
            },
        }
    def check(self):
        return inspect_bundle(snapshot=self.snapshot,manifest=self.manifest,
                              files=self.files)
    def test_genuine_static_fixture_passes(self):
        result=self.check()
        self.assertEqual(result["status"],"OWNER_REVIEWED_HISTORICAL_BUNDLE_HASH_MATCH")
        self.assertFalse(result["live_news_verified"])
        self.assertFalse(result["auto_regenerated_on_revision_change"])
    def test_revision_change_blocks_old_pdf_and_docx(self):
        self.snapshot["snapshot_meta"]["revision"]="different-revision"
        with self.assertRaisesRegex(ValueError,"snapshot_revision_artifact_mismatch"):self.check()
    def test_changed_fact_blocks_old_report(self):
        self.snapshot["stories"][0]["what_happened"]="اختراع معلومة مالية"
        with self.assertRaisesRegex(ValueError,"snapshot_facts_artifact_mismatch"):self.check()
    def test_pdf_tamper_blocks_both_downloads(self):
        self.files["pdf"]+=b"x"
        with self.assertRaisesRegex(ValueError,"artifact_integrity_mismatch_pdf"):self.check()
    def test_word_tamper_blocks_both_downloads(self):
        self.files["docx"]+=b"x"
        with self.assertRaisesRegex(ValueError,"artifact_integrity_mismatch_docx"):self.check()
    def test_missing_artifact_blocks_both_downloads(self):
        del self.files["docx"]
        with self.assertRaisesRegex(ValueError,"missing_artifact_bytes"):self.check()
    def test_false_live_claim_blocks_downloads(self):
        self.snapshot["snapshot_meta"]["source_live_connected"]=True
        with self.assertRaisesRegex(ValueError,"live_freshness_not_verified"):self.check()
    def test_future_verified_news_without_evidence_blocks(self):
        self.snapshot["snapshot_meta"]["source_new_verified_news_count"]=1
        with self.assertRaisesRegex(ValueError,"live_freshness_not_verified"):self.check()
    def test_original_image_upgrade_without_receipt_blocks(self):
        self.snapshot["stories"][1]["verification"]="ORIGINAL_VERIFIED"
        with self.assertRaisesRegex(ValueError,"unsupported_original_image_claim"):self.check()
    def test_wrong_manifest_sha_rejected(self):
        self.manifest["canonical_snapshot_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"snapshot_facts_artifact_mismatch"):self.check()
    def test_cannot_claim_email_delivered(self):
        self.snapshot["email_sent"]=True
        with self.assertRaisesRegex(ValueError,"false_live_or_delivery_claim"):self.check()
    def test_pdf_header_corruption_rejected_even_with_matching_hash(self):
        self.files["pdf"]=b"BADPDF"
        info=self.manifest["artifacts"]["pdf"]
        info["sha256"]=digest(self.files["pdf"]);info["size"]=len(self.files["pdf"])
        with self.assertRaisesRegex(ValueError,"malformed_pdf"):self.check()

if __name__=="__main__":unittest.main()
