"""Evidence-led visual QA for a genuine bad Al-Massa screenshot, NO REAL ASSETS.

Real 17-Nov RASD Inbox Word contained one original Al-Massa screenshot whose
article title and sidebar were readable but whose article hero was a uniform
pale placeholder in the MAIN right content region. Synthetic fixtures below
are NOT user news, original screenshots or publishable evidence. The check
does not use OCR, bypass approved domains or edit rejected screenshots.
"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from capture_public import (
    accept_staged_image, image_quality,
    suspicious_flat_massa_original_lead,
)


def fixture(*, loaded=False):
    image = Image.new("RGB", (1200, 900), (246, 246, 246))
    d = ImageDraw.Draw(image)
    # Authentic-looking browser page structure, but SYNTHETIC only:
    # banner text, unrelated sidebar, and deliberately blank right hero.
    d.rectangle((0, 0, 1200, 62), fill=(238, 237, 236))
    d.rectangle((0, 6, 1200, 12), fill=(70, 72, 77))
    d.rectangle((0, 64, 350, 900), fill=(245, 240, 234))
    for y in (100, 230, 350, 475, 630, 760):
        d.rectangle((12, y, 315, y + 28), fill=(80, 84, 85))
    d.rectangle((460, 110, 1120, 148), fill=(25, 25, 27))
    d.rectangle((490, 165, 1110, 184), fill=(48, 48, 51))
    if loaded:
        # Genuine varied ORIGINAL hero pixels would occupy the right
        # content region. Do not replace bad capture with this fixture.
        for j in range(25):
            d.rectangle((450 + j*24, 395, 469 + j*24, 730),
                        fill=((20+j*7)%255, (63+j*9)%255, (40+j*11)%255))
    return image


class RealMassaFailureContractNoSend(unittest.TestCase):
    def test_empty_main_publisher_hero_is_a_hold_even_with_lively_sidebar(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/"synthetic-bad.jpg"
            fixture().save(p, format="JPEG", quality=88)
            result = image_quality(p, publisher="gomhuriaonline.com")
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason"],
                             "unloaded_massa_article_lead_media")

    def test_same_synthetic_pattern_not_global_other_publisher_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/"synthetic-bad.jpg"
            fixture().save(p, format="JPEG", quality=88)
            result = image_quality(p, publisher="alborsaanews.com")
            self.assertTrue(result["accepted"])
            self.assertEqual(result["reason"], "ok")

    def test_loaded_varied_main_image_is_allowed_on_massa(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/"synthetic-loaded.jpg"
            fixture(loaded=True).save(p, format="JPEG", quality=88)
            result = image_quality(p, publisher="gomhuriaonline.com")
            self.assertTrue(result["accepted"])

    def test_previously_verified_destination_never_overwritten_by_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            old = base/"already-verified.jpg"
            old.write_bytes(b"verified-existing-data")
            staged = base/"test-only.jpg"
            fixture().save(staged, format="JPEG", quality=88)
            outcome = accept_staged_image(
                staged, old, publisher="gomhuriaonline.com")
            self.assertFalse(outcome["ok"])
            self.assertEqual(outcome["reason"],
                             "visual_qa_unloaded_massa_article_lead_media")
            self.assertEqual(old.read_bytes(), b"verified-existing-data")
            self.assertTrue(staged.exists())

    def test_rejected_photo_is_never_accepted_by_visual_gate(self):
        image = fixture()
        self.assertTrue(suspicious_flat_massa_original_lead(image))
        self.assertFalse(suspicious_flat_massa_original_lead(
            fixture(loaded=True)))


if __name__ == "__main__":
    unittest.main()
