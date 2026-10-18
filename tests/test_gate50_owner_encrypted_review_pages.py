"""Gate50: original Word pages encrypted with owner RSA/AES, integrity, HOLD.

Fixtures are synthetic and NEVER evidence of publisher coverage or human review.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

from gate43_owner_encrypted_review import pack_owner_review, unpack_owner_review
from test_gate43_owner_encrypted_review import _keys, audit

ROOT = Path(__file__).resolve().parents[1]


def synthetic_private_page(directory, number):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"page-{number:03d}.png"
    im = Image.new("RGB", (900, 1150), "white")
    d = ImageDraw.Draw(im)
    for n in range(0, 1150, 18):
        d.rectangle((28, n, 870, n + 7),
                    fill=((n + 40 * number) % 180 + 20, 35, 85))
    im.save(target, "PNG")
    assert target.stat().st_size >= 5000
    return target


def synthetic_word(directory):
    output = directory / "RASD-Unified-2026-10-17.docx"
    doc = Document()
    doc.add_paragraph("مصدر الوزارة الرسمي — مستند اصطناعي للاختبار فقط")
    doc.save(output)
    return output


class OwnerEncryptedPrivatePageTests(unittest.TestCase):
    def test_two_review_pages_and_word_only_inside_encrypted_owner_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pub, private = _keys(root)
            folder = root / "reports"
            folder.mkdir()
            word = synthetic_word(folder)
            pages = root / "review-pages"
            images = [synthetic_private_page(pages, i) for i in (1, 2)]
            ciphertext_file = root / "encrypted.json"
            receipt = pack_owner_review(
                folder, audit("READY_QA_ONLY"), ciphertext_file, pub,
                render_passed=True, review_pages_dir=pages)
            self.assertTrue(receipt["encrypted"])
            self.assertTrue(receipt["owner_review_word_included"])
            self.assertTrue(receipt["owner_review_pages_encrypted"])
            self.assertEqual(receipt["owner_review_page_count"], 2)
            ciphertext = ciphertext_file.read_bytes()
            self.assertNotIn(b"\x89PNG", ciphertext)
            self.assertNotIn(b"RASD-Unified-2026-10-17.docx", ciphertext)
            self.assertNotIn(b"page-001.png", ciphertext)
            recovered = root / "owner-decrypted"
            names = unpack_owner_review(ciphertext_file, private, recovered)
            self.assertEqual(set(names), {
                word.name, "rasd-owner-review-audit.json",
                "rasd-owner-review-pages-manifest.json",
                "review-pages/page-001.png", "review-pages/page-002.png",
            })
            self.assertEqual((recovered / word.name).read_bytes(), word.read_bytes())
            manifest = json.loads((recovered /
                "rasd-owner-review-pages-manifest.json").read_text())
            for index, image in enumerate(images, 1):
                png = recovered / f"review-pages/page-{index:03d}.png"
                self.assertEqual(png.read_bytes(), image.read_bytes())
                self.assertEqual(manifest["pages"][index-1]["sha256"],
                                 hashlib.sha256(image.read_bytes()).hexdigest())
            private_audit = json.loads((recovered /
                "rasd-owner-review-audit.json").read_text())
            self.assertEqual(private_audit["owner_review_page_count"], 2)
            self.assertTrue(private_audit["owner_review_pages_encrypted"])
            self.assertFalse(private_audit["human_visual_review"])
            self.assertFalse(private_audit["production_delivery_approved"])

    def test_hold_cannot_package_any_raster_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pub, _ = _keys(root)
            pages = root / "pages"
            synthetic_private_page(pages, 1)
            with self.assertRaisesRegex(ValueError, "review_pages_forbidden_on_hold"):
                pack_owner_review(root, audit("HOLD"),
                                  root / "cipher.json", pub,
                                  review_pages_dir=pages)
            self.assertFalse((root / "cipher.json").exists())

    def test_invalid_gap_or_corrupt_png_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pub, _ = _keys(root)
            source = root / "reports"
            source.mkdir()
            synthetic_word(source)
            pages = root / "pages"
            synthetic_private_page(pages, 2)
            with self.assertRaisesRegex(ValueError, "owner_review_page_name_invalid"):
                pack_owner_review(source, audit("READY_QA_ONLY"),
                                  root / "cipher.json", pub, render_passed=True,
                                  review_pages_dir=pages)
            (pages / "page-002.png").rename(pages / "page-001.png")
            (pages / "page-001.png").write_bytes(b"not a PNG" * 1000)
            with self.assertRaisesRegex(ValueError, "owner_review_page_not_valid_png"):
                pack_owner_review(source, audit("READY_QA_ONLY"),
                                  root / "cipher.json", pub, render_passed=True,
                                  review_pages_dir=pages)
            self.assertFalse((root / "cipher.json").exists())

    def test_owner_manual_workflow_never_uploads_plaintext_review_pages(self):
        content = (ROOT / ".github/workflows/report-unified-ministry-manual.yml").read_text()
        self.assertIn('review_pages_dir=root / "rasd-private-review-pages"', content)
        self.assertIn("if rendered else None", content)
        self.assertIn("owner_review_pages_encrypted", content)
        self.assertIn("retention-days: 1", content)
        self.assertIn("path: " + chr(36) + "{{ runner.temp }}/rasd-g43-owner-encrypted.json", content)
        self.assertNotIn("path: " + chr(36) + "{{ runner.temp }}/rasd-private-review-pages", content)
        self.assertNotIn("schedule:", content)
        self.assertNotIn("send_email(", content)


if __name__ == "__main__":
    unittest.main()
