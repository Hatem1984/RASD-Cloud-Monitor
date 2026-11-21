"""Heavy no-send proof: daily volumes never lose or swap genuine JPEG bytes.

Photos here are synthetic, intentionally high-entropy to make Word size
realistic. NEVER sent or substituted for publisher evidence.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from monitor import article_id
from rasd_daily_volume_preflight_no_send import create_verified_daily_volumes


class BoundedLosslessDailyVolumesNoSend(unittest.TestCase):
    def make_archive(self, root: Path, number: int, *, noisy: bool):
        articles, proofs = [], []
        for i in range(number):
            image = root / f"original-{i:03d}.jpg"
            if noisy:
                # Realistic high-entropy JPEG, unlike tiny blank dummy photos.
                pic = Image.effect_noise((1700, 1200), 70).convert("RGB")
            else:
                pic = Image.new("RGB", (850, 650), "white")
                brush = ImageDraw.Draw(pic)
                brush.rectangle((0, 0, 849, 90), fill=(11, 32, 70))
                for y in range(120, 620, 35):
                    brush.rectangle((40, y, 800, y + 11), fill=(70, 110, 150))
            # Different original article pages must have distinct image bytes.
            # Identical white fixtures were incorrectly being deduplicated by
            # python-docx, which rightly violates the strict 1:1 image check.
            x = 60 + (i % 40) * 14
            y = 260 + (i // 40) * 27
            ImageDraw.Draw(pic).rectangle((x, y, x + 11, y + 12),
                                          fill=((i * 17) % 255, 30, 95))
            pic.save(image, "JPEG", quality=88)
            url = f"https://hapijournal.com/2026/11/21/real-shaped-dummy-{i}"
            articles.append({
                "id": article_id(url),
                "headline": f"وزارة التخطيط | خبر صورة اختبار رقم {i+1}",
                "url": url, "source": "Hapi native news RSS",
                "published_at_cairo": "2026-11-21 12:20 EET",
                "published_display_cairo": "21 نوفمبر 2026",
                "publisher_excerpt": "صورة صناعية لأغراض إثبات السعة فقط",
                "evidence_image_path": str(image)})
            proofs.append({
                "status": "verified",
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest()})
        return articles, proofs

    def package(self, rows, proofs, folder, *, size=4_000_000):
        return create_verified_daily_volumes(
            rows, proofs, folder,
            title="رصد | التقرير المجمع اليومي — إثبات دون إرسال",
            start="20 نوفمبر 22:00 بتوقيت القاهرة",
            end="21 نوفمبر 22:00 بتوقيت القاهرة",
            max_word_bytes=size)

    def test_22_large_jpegs_split_without_missing_story_digest_or_bad_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles, proof = self.make_archive(root, 22, noisy=True)
            volumes = self.package(articles, proof, root / "volumes")
            self.assertGreater(len(volumes), 1)
            self.assertLessEqual(len(volumes), 32)
            self.assertEqual([x for vol in volumes for x in vol["article_ids"]],
                             [row["id"] for row in articles])
            self.assertEqual([x for vol in volumes for x in vol["sha256"]],
                             [row["sha256"] for row in proof])
            self.assertEqual(sum(v["count"] for v in volumes), 22)
            for volume in volumes:
                self.assertLessEqual(volume["bytes"], 4_000_000)
                doc = Document(volume["path"])
                self.assertEqual(len(doc.inline_shapes), volume["count"])
                self.assertIn(f"الجزء {volume['part']} من {volume['parts']}",
                              doc.tables[0].cell(0, 0).text)
            self.assertTrue(all(
                word_images_match_capture_digests(
                    v["path"], proof[sum(x["count"] for x in volumes[:i]):
                                     sum(x["count"] for x in volumes[:i+1])])
                for i, v in enumerate(volumes)))

    def test_wrong_sha_refuses_all_volumes_before_any_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles, proof = self.make_archive(root, 3, noisy=False)
            proof[1]["sha256"] = "0" * 64
            target = root / "volumes"
            with self.assertRaisesRegex(RuntimeError,
                                        "daily_volume_original_image_digest_hold"):
                self.package(articles, proof, target)
            self.assertFalse(target.exists())

    def test_one_unbounded_photo_is_hold_without_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles, proof = self.make_archive(root, 1, noisy=True)
            target = root / "volumes"
            with self.assertRaisesRegex(RuntimeError,
                                        "daily_volume_single_original_too_large_hold"):
                self.package(articles, proof, target, size=1_200_000)
            self.assertFalse(target.exists())

    def test_168_covered_original_cards_are_complete_when_images_small(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles, proof = self.make_archive(root, 168, noisy=False)
            volumes = self.package(articles, proof, root / "volumes")
            self.assertEqual(sum(v["count"] for v in volumes), 168)
            self.assertEqual([x for v in volumes for x in v["article_ids"]],
                             [x["id"] for x in articles])
            self.assertEqual([x for v in volumes for x in v["sha256"]],
                             [x["sha256"] for x in proof])


if __name__ == "__main__":
    unittest.main()
