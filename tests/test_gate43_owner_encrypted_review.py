"""Gate43 encrypted owner review and manual workflow safety regression.

Encrypted fixture bytes are synthetic and NOT publisher evidence.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from docx import Document

from gate43_owner_encrypted_review import pack_owner_review, unpack_owner_review

ROOT = Path(__file__).resolve().parents[1]


def _keys(root):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pk = root / "owner-private.pem"
    pub = root / "owner-public.pem"
    pk.write_bytes(private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    pub.write_bytes(private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo))
    return pub, pk


def audit(status):
    return {
        "mode": "stage2_ministry_unified_word_ephemeral_qa",
        "status": status,
        "target_date_cairo": "2026-10-17",
        "screenshots_missing": 0,
        "screenshots_verified": 1,
        "selected_unique_articles": 1,
        "word_images_verified": True,
        "all_sources_healthy": True,
        "email_sent": False,
        "scheduler_enabled": False,
        "source_added_to_production": False,
        "origin_url_secret_test_only": "NEVER_IN_OWNER_ARCHIVE",
    }


class OwnerOnlyEncryptedUnificationTests(unittest.TestCase):
    def test_verified_word_only_as_ciphertext_and_safe_local_decrypt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pub, pk = _keys(root)
            report = root / "reports"
            report.mkdir()
            filename = "RASD-Unified-2026-10-17.docx"
            document = Document()
            document.add_paragraph("Synthetic official Ministry Word fixture only")
            document.save(report / filename)
            final_bytes = (report / filename).read_bytes()
            payload = root / "encrypted.json"
            receipt = pack_owner_review(
                report, audit("READY_QA_ONLY"), payload, pub,
                render_passed=True)
            self.assertTrue(receipt["encrypted"])
            self.assertFalse(receipt["plaintext_artifact"])
            self.assertTrue(receipt["owner_review_word_included"])
            cipher = payload.read_bytes()
            self.assertNotIn(b"PK\\x03\\x04", cipher)
            self.assertNotIn(b"Synthetic official Ministry", cipher)
            self.assertNotIn(b"NEVER_IN_OWNER_ARCHIVE", cipher)
            destination = root / "owner-review"
            files = unpack_owner_review(payload, pk, destination)
            self.assertEqual(set(files), {filename, "rasd-owner-review-audit.json"})
            self.assertEqual((destination / filename).read_bytes(), final_bytes)
            parsed = json.loads((destination / "rasd-owner-review-audit.json").read_text())
            self.assertFalse(parsed["human_visual_review"])
            self.assertFalse(parsed["production_delivery_approved"])
            self.assertNotIn("origin_url_secret_test_only", parsed)

    def test_holds_never_bundle_or_upload_word(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pub, pk = _keys(root)
            payload = root / "cipher.json"
            receipt = pack_owner_review(
                root, audit("HOLD"), payload, pub)
            self.assertFalse(receipt["owner_review_word_included"])
            files = unpack_owner_review(payload, pk, root / "received")
            self.assertEqual(files, ["rasd-owner-review-audit.json"])

    def test_partial_word_or_unverified_render_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pub, pk = _keys(root)
            docx = root / "RASD-Unified-2026-10-17.docx"
            docx.write_bytes(b"unverified-test-placeholder")
            with self.assertRaises(ValueError):
                pack_owner_review(root, audit("HOLD"), root / "cipher.json", pub)
            with self.assertRaises(ValueError):
                pack_owner_review(root, audit("READY_QA_ONLY"),
                                  root / "cipher.json", pub, render_passed=False)
            unsafe = audit("READY_QA_ONLY")
            unsafe["email_sent"] = True
            with self.assertRaises(ValueError):
                pack_owner_review(root, unsafe, root / "cipher.json", pub,
                                  render_passed=True)

    def test_ciphertext_tamper_is_not_accepted(self):
        import base64
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pub, pk = _keys(root)
            payload = root / "cipher.json"
            pack_owner_review(root, audit("HOLD"), payload, pub)
            data = json.loads(payload.read_text())
            encrypted = bytearray(base64.b64decode(data["ciphertext"]))
            encrypted[-1] ^= 1
            data["ciphertext"] = base64.b64encode(encrypted).decode()
            payload.write_text(json.dumps(data))
            with self.assertRaises(Exception):
                unpack_owner_review(payload, pk, root / "received")

    def test_owner_manual_workflow_uses_exact_sources_and_no_send_or_plaintext_upload(self):
        workflow = (ROOT / ".github/workflows/report-unified-ministry-manual.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.actor == 'Hatem1984'", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("unified_ministry_word.py", workflow)
        self.assertIn("word_render_audit", workflow)
        self.assertIn("gate43_owner_encrypted_review", workflow)
        self.assertIn("gate26_owner_review_pubkey.pem", (
            ROOT / "gate43_owner_encrypted_review.py").read_text())
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("gmail", workflow.lower().replace("no gmail", ""))
        self.assertIn("path: ${{ runner.temp }}/rasd-g43-owner-encrypted.json", workflow)
        self.assertNotIn("path: ${{ runner.temp }}/rasd-unified-private", workflow)
        self.assertIn("retention-days: 1", workflow)


if __name__ == "__main__":
    unittest.main()
