"""Approved source probe and 4-draft safety, all offline mocked."""
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import rasd_four_reports_no_send as subject

NOW = datetime(2026, 11, 8, 21, 10, tzinfo=timezone.utc)


class FourReportNoSendTest(unittest.TestCase):
    def test_default_no_network_no_mail_and_four_status_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "drafts"
            with patch.object(
                    subject, "approved_web_probe",
                    side_effect=AssertionError("web_probe_must_not_run")):
                result = subject.run_no_send(
                    now=NOW, final_day=date(2026, 11, 8),
                    output=out, probe_web=False)
            self.assertFalse(result["smtp_sent"])
            self.assertFalse(result["scheduler_changed"])
            self.assertEqual(len(list(out.glob("*.docx"))), 4)
            self.assertTrue(all(v["items"] == 0
                                for v in result["reports"].values()))
            self.assertEqual(result["social_live_posts_verified"], 0)
            self.assertFalse(result["daily_archive_read"])

    def test_approved_web_capture_is_url_date_and_jpeg_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = json.loads((Path(subject.__file__).with_name(
                "sources_newsroom_active.json")).read_text(encoding="utf-8"))
            profile = config["feeds"][0]
            url = "https://" + profile["allowed_article_hosts"][0] + "/2026/test-qa"
            captured = []
            def fake_discover(cfg, now, *, allow_degraded, source_records, age_hours):
                self.assertTrue(allow_degraded)
                self.assertEqual(age_hours, 24)
                source_records.extend({
                    "feed_id": f["id"], "status": "ok", "verified_links": 1
                } for f in cfg["feeds"])
                return [{
                    "headline": "عنوان خبر اختباري غير حقيقي",
                    "source": profile["name"], "url": url,
                    "published_at_cairo": "2026-11-08 22:15 EET",
                }]
            def fake_capture(candidate, feeds, destination):
                captured.append(candidate["url"])
                Image.new("RGB", (750, 900), "white").save(destination, "JPEG")
                return {"status": "verified", "sha256":
                        hashlib.sha256(destination.read_bytes()).hexdigest()}
            rows, states = subject.approved_web_probe(
                now=NOW, evidence_root=root,
                discover=fake_discover, capture=fake_capture)
            self.assertEqual(len(rows), 1)
            self.assertEqual(captured, [url])
            self.assertEqual(len(states), len(config["feeds"]))
            self.assertEqual(states[0]["status"], "ok")
            self.assertEqual(rows[0]["capture_receipt"]["url"], url)
            self.assertEqual(rows[0]["published_at"], "2026-11-08T20:15:00+00:00")

    def test_failed_original_capture_is_hold_not_delivered(self):
        with tempfile.TemporaryDirectory() as folder:
            config = json.loads((Path(subject.__file__).with_name(
                "sources_newsroom_active.json")).read_text(encoding="utf-8"))
            profile = config["feeds"][0]
            def discover(cfg, now, *, allow_degraded, source_records, age_hours):
                source_records.extend({
                    "feed_id": f["id"], "status": "ok", "verified_links": 1
                } for f in cfg["feeds"])
                return [{"source": profile["name"], "headline": "معلق للاختبار",
                         "url": "https://" + profile["allowed_article_hosts"][0]
                                + "/news/mock",
                         "published_at_cairo": "2026-11-08 22:15 EET"}]
            rows, states = subject.approved_web_probe(
                now=NOW, evidence_root=Path(folder),
                discover=discover, capture=lambda *x: {"status": "hold"})
            self.assertEqual(rows, [])
            self.assertEqual(states[0]["status"], "hold")


if __name__ == "__main__":
    unittest.main()
