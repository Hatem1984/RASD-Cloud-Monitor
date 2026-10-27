"""MA'AL V0.2 local API acceptance — immutable data and no action transport."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parent
sys.path.insert(0,str(APP.parent))
sys.path.insert(0, str(APP))
import server

BASE = "http://127.0.0.1:52320"

class ReadOnlyContractTests(unittest.TestCase):
    def test_snapshot_is_configured_not_live(self):
        data = server.get_snapshot()
        self.assertEqual((data["active_feeds"], data["keywords"], data["research_sources"]), (13,29,50))
        self.assertFalse(data["live"])
        self.assertFalse(data["production_writes"])
        self.assertEqual(len(data["sources"]),13)
        self.assertEqual({row["health"] for row in data["sources"]},{"NOT_LIVE_CHECKED"})

    def test_official_case_is_synthetic_and_non_executable(self):
        data = server.get_case()
        self.assertEqual(data["record_type"],"HISTORICAL_VERIFIED_DEMO")
        self.assertTrue(data["verified_receipt"])
        self.assertTrue(data["synthetic_company"])
        self.assertFalse(data["actions_enabled"])
        self.assertFalse(data["email_sent"])
        self.assertEqual(data["published_day"],"2026-10-17")
        self.assertEqual(data["publication_precision"],"DATE_ONLY")
        self.assertIsNone(data["financial_impact"])
        self.assertEqual(len(data["proposals"]),2)

    def test_tampering_evidence_binary_fails_closed(self):
        with patch.object(server, "CASE_IMAGE", APP/"index.html"):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                server.get_case()

    def test_tampering_official_receipt_fails_closed(self):
        raw=json.loads(server.CASE_JSON.read_text(encoding="utf-8"))
        raw["external_actions_executed"]=True
        with patch.object(server.CASE_JSON.__class__,"read_text",return_value=json.dumps(raw)):
            with self.assertRaisesRegex(ValueError,"Unapproved demo receipt"):
                server.get_case()

    def test_http_allows_exact_allowlist_only(self):
        for path in ("/","/style.css","/app.js","/brand-symbol.png",
                     "/api/snapshot","/api/case","/api/case-image"):
            with self.subTest(path=path):
                response=urllib.request.urlopen(BASE+path,timeout=10)
                self.assertEqual(response.status,200)
                self.assertIn("default-src 'self'",response.headers["Content-Security-Policy"])
                self.assertEqual(response.headers["X-Frame-Options"],"DENY")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(BASE+"/../../02_PRIVATE_OWNER/data",timeout=10)
        self.assertEqual(ctx.exception.code,404)

    def test_http_post_not_authorized(self):
        req=urllib.request.Request(BASE+"/api/case",data=b"approve=1",method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req,timeout=10)
        self.assertEqual(ctx.exception.code,405)

    def test_evidence_registry_is_historical_and_never_live(self):
        data=json.load(urllib.request.urlopen(BASE+"/api/evidence",timeout=10))
        self.assertEqual(data["schema"],"MAAL_EVIDENCE_LIST_V1")
        self.assertFalse(data["live_feed_connection"])
        self.assertFalse(data["private_ledger_exposed"])
        self.assertEqual(len(data["items"]),1)
        item=data["items"][0]
        self.assertEqual(item["timeliness"],"HISTORICAL")
        self.assertEqual(item["status"],"VERIFIED_ORIGINAL_PAGE")
        self.assertEqual(item["publication_precision"],"DATE_ONLY")
        self.assertEqual(item["original_sha256"],server.get_case()["evidence_digest"])

    def test_verified_word_report_contains_exact_original_image(self):
        from zipfile import ZipFile
        from io import BytesIO
        raw=server.get_verified_report_bytes()
        with ZipFile(BytesIO(raw)) as doc:
            imgs=[n for n in doc.namelist() if n.startswith("word/media/")]
            self.assertEqual(len(imgs),1)
            self.assertEqual(hashlib.sha256(doc.read(imgs[0])).hexdigest(),
                             server.get_case()["evidence_digest"])
        response=urllib.request.urlopen(BASE+"/api/case-report",timeout=10)
        self.assertEqual(response.status,200)
        self.assertIn("attachment;",response.headers["Content-Disposition"])

    def test_tampering_word_image_blocks_export(self):
        with patch.object(server,"CASE_REPORT",APP/"index.html"):
            with self.assertRaises(ValueError):
                server.get_verified_report_bytes()

    def test_sources_expose_only_public_read_only_feed_policy(self):
        data=server.get_snapshot()
        self.assertEqual(len(data["sources"]),13)
        for row in data["sources"]:
            self.assertTrue(row["feed_url"].startswith("https://"))
            self.assertGreaterEqual(len(row["allowed_article_hosts"]),1)
            self.assertEqual(row["health"],"NOT_LIVE_CHECKED")

    def test_upload_and_post_disabled(self):
        req=urllib.request.Request(BASE+"/api/case-report",data=b"approve=1",method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req,timeout=10)
        self.assertEqual(ctx.exception.code,405)

    def test_verified_http_original_jpeg_matches_receipt(self):
        sample=server.get_case()
        actual=urllib.request.urlopen(BASE+"/api/case-image",timeout=10).read()
        self.assertEqual(hashlib.sha256(actual).hexdigest(),sample["evidence_digest"])

if __name__ == "__main__":
    unittest.main()
