"""Offline acceptance checks for publisher-page screenshot requirements."""
import tempfile
import unittest
from pathlib import Path
from cloud_proof_report import proof_capture
from monitor import article_id

URL = "https://hapijournal.com/example"
ARTICLE = {"id": article_id(URL), "url": URL,
           "headline": "وزارة التخطيط تعقد اجتماعا", "source": "Hapi native news RSS"}
FEEDS = [{"name": "Hapi native news RSS",
          "allowed_article_hosts": ["hapijournal.com", "www.hapijournal.com"]}]


class PublisherProofTests(unittest.TestCase):
    def test_blocked_page_is_not_considered_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = proof_capture(ARTICLE, FEEDS, Path(directory) / "evidence.jpg",
                                   capture=lambda *args: {
                                       "ok": False, "reason": "publisher_access_refused"})
        self.assertEqual(result["status"], "hold")

    def test_missing_image_never_passes_even_if_capture_claims_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result = proof_capture(ARTICLE, FEEDS, Path(directory) / "evidence.jpg",
                                   capture=lambda *args: {
                                       "ok": True, "actual_url": URL,
                                       "title": ARTICLE["headline"]})
        self.assertEqual(result["reason"], "screenshot_too_small")

    def test_redirected_to_different_article_never_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = proof_capture(ARTICLE, FEEDS, Path(directory) / "evidence.jpg",
                                   capture=lambda *args: {
                                       "ok": True,
                                       "actual_url": "https://hapijournal.com/other-story",
                                       "title": ARTICLE["headline"]})
        self.assertEqual(result["reason"], "url_mismatch")


if __name__ == "__main__":
    unittest.main()
