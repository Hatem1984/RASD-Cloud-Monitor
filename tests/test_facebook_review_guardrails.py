"""RASD Facebook local review guardrails; synthetic fixtures only, no Meta IO."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from facebook_manual_evidence import build_manual_facebook_report
from facebook_manual_validation import (
    INDEX_NAME, identity_digest, parse_operator_post_time, post_identity,
    read_local_index,
)


NOW = datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc)


def entry(image: Path, *, url: str = "https://facebook.com/123/posts/456"):
    return {
        "url": url, "source": "صفحة اختبار محلية - غير حقيقية",
        "screenshot": str(image),
        "published_at": "2026-11-08T11:00:00+02:00",
        "privacy_checked": True,
        "note": "لقطة اختبار مصطنعة لا تمثل منشورًا حقيقيًا",
    }


class FacebookReviewGuardrails(unittest.TestCase):
    def test_canonical_direct_and_story_link_duplicate_identity(self):
        direct = "https://www.facebook.com/123/posts/456?fbclid=test"
        mobile = "https://m.facebook.com/story.php?story_fbid=456&id=123"
        self.assertEqual(post_identity(direct), post_identity(mobile))
        self.assertEqual(identity_digest(direct), identity_digest(mobile))
        for non_post in (
            "https://facebook.com/123", "https://facebook.com/",
            "https://facebook.com/123/posts/456#tracking",
            "https://facebook.com/123/posts/456?access_token=secret",
        ):
            self.assertIsNone(post_identity(non_post))

    def test_post_date_must_have_zone_and_cannot_be_future(self):
        self.assertEqual(
            parse_operator_post_time("2026-11-08T11:00:00+02:00", now=NOW).year,
            2026)
        for invalid in (
            "2026-11-08", "2026-11-08 11:00", "2026-11-08T11:00:00",
            "2026-11-09T13:00:00+02:00", "2026-11-08T99:00:00+02:00",
        ):
            with self.subTest(value=invalid):
                with self.assertRaisesRegex(ValueError, "facebook_post_date_hold"):
                    parse_operator_post_time(invalid, now=NOW)

    def test_privacy_source_and_date_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            img = root / "screen.png"
            Image.new("RGB", (500, 280), "white").save(img)
            good = entry(img)
            for changes in (
                {"privacy_checked": False},
                {"source": ""},
                {"published_at": "2026-11-08"},
            ):
                with self.assertRaises(ValueError):
                    build_manual_facebook_report(
                        [{**good, **changes}], root / "reports", now=NOW)
            self.assertFalse(list((root / "reports").glob("*.docx")))

    def test_index_stops_cross_report_duplicate_without_storing_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pic = root / "screenshot.png"
            Image.new("RGB", (450, 320), "white").save(pic)
            reports = root / "reports"
            first = build_manual_facebook_report([entry(pic)], reports, now=NOW)
            self.assertEqual(first["items"], 1)
            self.assertEqual(len(read_local_index(reports)), 1)
            index_text = (reports / INDEX_NAME).read_text(encoding="utf-8")
            self.assertNotIn("facebook.com", index_text)
            self.assertNotIn("صفحة اختبار", index_text)
            with self.assertRaisesRegex(
                    ValueError, "facebook_duplicate_prior_report_hold"):
                build_manual_facebook_report(
                    [entry(pic, url=(
                        "https://m.facebook.com/story.php?story_fbid=456&id=123"
                    ))], reports, now=NOW)
            self.assertEqual(len(list(reports.glob("*.docx"))), 1)

    def test_corrupted_index_fails_closed_and_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reports = root / "reports"
            reports.mkdir()
            index = reports / INDEX_NAME
            index.write_text('{"version":1,"ids":["bad"]}', encoding="utf-8")
            pic = root / "screen.png"
            Image.new("RGB", (500, 300), "white").save(pic)
            with self.assertRaisesRegex(
                    ValueError, "facebook_index_unreadable_hold"):
                build_manual_facebook_report([entry(pic)], reports, now=NOW)
            self.assertEqual(json.loads(index.read_text())["ids"], ["bad"])
            self.assertFalse(list(reports.glob("*.docx")))

    def test_research_candidates_never_activate_meta_graph(self):
        root = Path(__file__).resolve().parents[1]
        research = json.loads(
            (root / "facebook_page_research_candidates_20261108.json")
            .read_text(encoding="utf-8"))
        config = json.loads(
            (root / "facebook_pages_pilot.json").read_text(encoding="utf-8"))
        self.assertEqual(research["approval_status"], "NOT_APPROVED")
        self.assertEqual(len(research["candidates"]), 6)
        self.assertTrue(all(item["page_id"] is None for item in research["candidates"]))
        self.assertTrue(all(item["status"].startswith("HOLD")
                            for item in research["candidates"]))
        self.assertEqual(config["pages"], [])


if __name__ == "__main__":
    unittest.main()
