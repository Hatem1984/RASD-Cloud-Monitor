"""Official social discovery and four-Word QA: offline synthetic only."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from docx import Document

from rasd_social_official_intake import (
    collect_social, platform_json_get, collect_approved_facebook,
    collect_approved_x, _fb_post)
from rasd_social_original_capture import _identity_visible, capture_original_post
from rasd_social_review_bridge import approved_social_probe
from rasd_four_reports_no_send import run_no_send

NOW = datetime(2026, 11, 8, 20, 20, tzinfo=timezone.utc)
XPOST = "1234567890123456789"
XUSER = "9876543210123456789"
FBPAGE = "123456789"
FBPOST = "123456789_456789012"
KEYWORD = "وزارة التخطيط"
SCOPE = [KEYWORD]
FB = {
    "approved": True, "access_confirmed": True,
    "pages": [{"id": FBPAGE, "name": "صفحة وزارة التخطيط"}],
    "max_pages_per_page": 2, "max_posts_per_page": 25,
}
X = {
    "approved": True, "paid_api_cost_approved": True,
    "queries": ['"وزارة التخطيط"'],
    "max_pages_per_query": 1, "page_size": 10, "max_posts_per_run": 10,
}
ENV = {
    "RASD_META_PAGE_ACCESS_TOKEN": "mock-not-real-meta",
    "RASD_X_BEARER_TOKEN": "mock-not-real-x",
    "RASD_X_PAID_READ_APPROVED": "yes",
    "RASD_SOCIAL_ORIGINAL_CAPTURE_APPROVED": "yes",
}


def config():
    return {
        "schema_version": 1, "original_post_browser_capture_approved": False,
        "facebook": copy.deepcopy(FB), "x": copy.deepcopy(X),
        "instagram": {"approved": False},
        "linkedin": {"approved": False},
    }


def api(url, token, *, expected_host):
    p = urlsplit(url)
    q = parse_qs(p.query)
    if expected_host == "graph.facebook.com":
        assert p.path.endswith(f"/{FBPAGE}/published_posts")
        return {
            "data": [{
                "id": FBPOST, "message": "وزارة التخطيط تعلن بيانًا رسميًا عن الخطة",
                "created_time": "2026-11-08T21:30:00+0200",
                "permalink_url": f"https://www.facebook.com/{FBPAGE}/posts/456789012",
            }]
        }
    assert expected_host == "api.x.com"
    assert p.path == "/2/tweets/search/recent"
    assert q.get("query") == [X["queries"][0]]
    assert q.get("max_results") == ["10"]
    return {
        "data": [{
            "id": XPOST, "author_id": XUSER,
            "text": "وزارة التخطيط تناقش مستهدفات خطة التنمية الاقتصادية",
            "created_at": "2026-11-08T19:35:00.000Z",
        }],
        "includes": {"users": [{
            "id": XUSER, "username": "OfficialPlan", "name": "مسؤول تخطيط",
        }]},
        "meta": {"result_count": 1},
    }


class OfficialSocialNoSendQA(unittest.TestCase):
    def test_default_config_produces_four_hold_reports_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            def forbidden(*args, **kwargs):
                self.fail("No API or browser without config approval")
            from rasd_social_official_intake import CONFIG_PATH
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.assertFalse(raw["facebook"]["approved"])
            self.assertFalse(raw["x"]["paid_api_cost_approved"])
            result = collect_social(
                live=True, config=raw, now=NOW,
                getter=forbidden, environment=ENV)
            self.assertEqual(result["post_candidates"], [])
            self.assertEqual(result["sources"]["facebook"]["status"],
                             "not_configured")
            self.assertFalse(result["platform_api_access_proven"])

    def test_api_two_sources_realistic_metadata_without_screenshot(self):
        result = collect_social(
            live=True, config=config(), now=NOW, getter=api,
            environment=ENV)
        self.assertEqual(len(result["post_candidates"]), 2)
        self.assertEqual(result["sources"]["facebook"]["status"], "ok")
        self.assertEqual(result["sources"]["x"]["status"], "ok")
        self.assertEqual(result["original_screenshots_verified"], 0)
        self.assertEqual({r["platform"] for r in result["post_candidates"]},
                         {"facebook", "x"})
        self.assertTrue(all(r["evidence_status"] ==
                            "HOLD_ORIGINAL_POST_SCREENSHOT"
                            for r in result["post_candidates"]))
        self.assertFalse(result["smtp_sent"])

    def test_no_payment_gate_prevents_x_search(self):
        scope = config()
        env = {**ENV, "RASD_X_PAID_READ_APPROVED": "no"}
        hits = []
        def guarded(url, token, *, expected_host):
            hits.append(expected_host)
            return api(url, token, expected_host=expected_host)
        result = collect_social(
            live=True, config=scope, now=NOW, getter=guarded,
            environment=env)
        self.assertEqual(hits, ["graph.facebook.com"])
        self.assertEqual(result["sources"]["x"]["status"], "unauthorized")
        self.assertEqual(len(result["post_candidates"]), 1)

    def test_tokens_never_sent_as_query_parameters(self):
        urls = []
        def checked(url, token, *, expected_host):
            self.assertNotIn(token, url)
            self.assertEqual(urlsplit(url).scheme, "https")
            urls.append(url)
            return api(url, token, expected_host=expected_host)
        collect_social(live=True, config=config(), now=NOW,
                       getter=checked, environment=ENV)
        self.assertEqual(len(urls), 2)
        self.assertRaisesRegex(
            RuntimeError, "social_api_token_in_url_hold",
            platform_json_get,
            "https://api.x.com/2/tweets/search/recent?access_token=secret",
            "mock", expected_host="api.x.com")
        self.assertRaisesRegex(
            RuntimeError, "social_api_host_hold",
            platform_json_get, "https://api.x.com.attacker.invalid/path",
            "mock", expected_host="api.x.com")

    def test_x_pagination_limit_is_not_empty_or_complete(self):
        def truncated(url, token, *, expected_host):
            result = api(url, token, expected_host=expected_host)
            result["meta"]["next_token"] = "tokenNEXT123"
            return result
        start = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
        result = collect_approved_x(
            X, token="mock", start=start, end=end, keywords=SCOPE,
            getter=truncated)
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["queries_with_hold"], 1)

    def test_meta_cursor_fetch_more_than_25_without_url_following(self):
        calls = []
        def two_pages(url, token, *, expected_host):
            calls.append(url)
            if len(calls) == 1:
                return {"data": api(url, token, expected_host=expected_host)["data"],
                        "paging": {"next":
                           "https://evil.example/private?access_token=secret",
                           "cursors": {"after": "PAGECURSOR1"}}}
            self.assertIn("after=PAGECURSOR1", url)
            return {"data": []}
        start = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
        result = collect_approved_facebook(
            FB, token="mock", start=start, end=end, keywords=SCOPE,
            getter=two_pages)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("evil.example", calls[1])

    def test_spoofed_meta_post_url_and_page_identity_fail_closed(self):
        start = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
        fake = api("https://graph.facebook.com/v26.0/"
                   + FBPAGE + "/published_posts", "mock",
                   expected_host="graph.facebook.com")["data"][0]
        for diff in (
            {"id": "999999999_456789012"},
            {"permalink_url":
             "https://www.facebook.com.evil.invalid/123/posts/456"},
            {"created_time": "2026-11-09T21:30:00+0200"},
        ):
            with self.subTest(diff=diff):
                if "created_time" in diff:
                    self.assertIsNone(_fb_post(
                        {**fake, **diff}, {"id": FBPAGE, "name": "page"},
                        start=start, end=end, keywords=SCOPE))
                else:
                    with self.assertRaises(ValueError):
                        _fb_post(
                            {**fake, **diff},
                            {"id": FBPAGE, "name": "page"},
                            start=start, end=end, keywords=SCOPE)

    def test_capture_disabled_does_not_use_fake_image_or_email(self):
        with tempfile.TemporaryDirectory() as folder:
            def no_capture(*a, **k):
                self.fail("Browser must not open without separate authorization")
            conf = config()
            all_posts, statuses, details = approved_social_probe(
                now=NOW, evidence_root=Path(folder),
                collect=lambda **k: collect_social(
                    live=True, now=NOW, config=conf, getter=api,
                    environment=ENV),
                screenshot=no_capture, capture_originals=False,
                config=conf, environment=ENV)
            self.assertEqual(all_posts, [])
            self.assertEqual(details["api_candidates"], 2)
            self.assertEqual(details["original_capture_hold"], 2)
            self.assertEqual(details["independent_original_captures_verified"], 0)
            self.assertEqual(sum(s["status"] == "hold" for s in statuses), 2)
            self.assertFalse(details["smtp_sent"])

    def test_synthetic_capture_binds_social_hourly_word_only(self):
        with tempfile.TemporaryDirectory() as folder:
            conf = config()
            conf["original_post_browser_capture_approved"] = True
            def simulated(post, dest, *, owner_authorized):
                self.assertTrue(owner_authorized)
                Image.new("RGB", (490, 280),
                          "white" if post["platform"] == "facebook"
                          else "lightgray").save(dest, "PNG")
                return {
                    "status": "verified",
                    "url": post["url"], "platform_post_id": post["platform_post_id"],
                    "method": "authorized_platform_original_capture",
                    "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                }
            result = run_no_send(
                now=NOW, final_day=date(2026, 11, 8),
                output=Path(folder) / "reports",
                probe_social=True, capture_social=True,
                social_collector=lambda **k: collect_social(
                    live=True, now=NOW, config=conf,
                    getter=api, environment=ENV),
                social_screenshot=simulated,
                social_config=conf, social_environment=ENV)
            self.assertEqual(result["reports"]["social-hourly"]["items"], 2)
            self.assertEqual(result["reports"]["social-daily"]["items"], 0)
            self.assertEqual(result["reports"]["web-hourly"]["items"], 0)
            self.assertEqual(result["social_live_posts_verified"], 2)
            self.assertFalse(result["email_sent"])
            doc = Document(result["reports"]["social-hourly"]["path"])
            self.assertEqual(len(doc.inline_shapes), 2)
            self.assertEqual(
                len([r for r in doc.part.rels.values()
                     if r.reltype.endswith("/hyperlink")]), 2)

    def test_visible_identity_required_for_browser_evidence(self):
        self.assertFalse(_identity_visible(
            "Sign in to X to see what is happening",
            message="وزارة التخطيط تعلن الخطة الاستثمارية الجديدة",
            source="@OfficialPlan", platform="x"))
        self.assertTrue(_identity_visible(
            "@OfficialPlan وزارة التخطيط تعلن الخطة الاستثمارية الجديدة",
            message="وزارة التخطيط تعلن الخطة الاستثمارية الجديدة",
            source="@OfficialPlan", platform="x"))
        with tempfile.TemporaryDirectory() as folder:
            row = collect_social(
                live=True, config=config(), now=NOW,
                getter=api, environment=ENV)["post_candidates"][0]
            path = Path(folder) / "test.png"
            self.assertEqual(capture_original_post(
                row, path, owner_authorized=False)["status"], "hold")
            self.assertFalse(path.exists())

    def test_instagram_managed_professional_media_metadata_only(self):
        conf = config()
        conf["instagram"] = {
            "approved": True, "access_confirmed": True,
            "accounts": [{"id": "17841401234567890",
                          "username": "planning.eg"}],
            "max_pages_per_account": 1, "page_size": 25,
        }
        env = {**ENV, "RASD_INSTAGRAM_PAGE_ACCESS_TOKEN": "mock-ig-not-real"}
        def all_three(url, token, *, expected_host):
            if (expected_host == "graph.facebook.com" and
                    "/17841401234567890/media?" in url):
                return {"data": [{
                    "id": "18270815569115548",
                    "caption": "وزارة التخطيط ومتابعة خطة التنمية",
                    "timestamp": "2026-11-08T19:45:00+0000",
                    "username": "planning.eg",
                    "permalink": "https://www.instagram.com/p/ABC123xyz/",
                }]}
            return api(url, token, expected_host=expected_host)
        result = collect_social(
            live=True, config=conf, now=NOW,
            environment=env, getter=all_three)
        self.assertEqual(len(result["post_candidates"]), 3)
        self.assertEqual(result["sources"]["instagram"]["status"], "ok")
        self.assertEqual(result["original_screenshots_verified"], 0)
        self.assertEqual(result["sources"]["linkedin"]["status"],
                         "not_configured")
        self.assertTrue(any(p["platform"] == "instagram" and
                            p["url"].startswith("https://www.instagram.com/p/")
                            for p in result["post_candidates"]))

    def test_instagram_no_account_grant_does_not_make_api_requests(self):
        conf = config()
        conf["facebook"]["approved"] = False
        conf["x"]["approved"] = False
        conf["instagram"] = {
            "approved": True, "access_confirmed": True,
            "accounts": [{"id": "17841401234567890",
                          "username": "planning.eg"}],
            "max_pages_per_account": 1, "page_size": 25,
        }
        def no_network(*args, **kwargs):
            self.fail("Missing IG Page access token must block read")
        result = collect_social(
            live=True, config=conf, now=NOW,
            environment=ENV, getter=no_network)
        self.assertEqual(result["sources"]["instagram"]["status"],
                         "unauthorized")
        self.assertEqual(result["post_candidates"], [])

    def test_instagram_other_account_and_unverified_permalink_hold(self):
        from rasd_social_official_intake import _ig_post
        start = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
        row = {
            "id": "18270815569115548",
            "caption": "وزارة التخطيط تصدر بيانا جديدا",
            "timestamp": "2026-11-08T19:45:00Z",
            "username": "another.account",
            "permalink": "https://www.instagram.com/p/ABC123xyz/",
        }
        with self.assertRaisesRegex(ValueError, "instagram_owner_identity"):
            _ig_post(row, {"username": "planning.eg"}, start=start,
                     end=end, keywords=SCOPE)
        with self.assertRaisesRegex(ValueError, "instagram_original_link"):
            _ig_post(
                {**row, "username": "planning.eg",
                 "permalink": "https://instagram.com.evil.invalid/p/123"},
                {"username": "planning.eg"}, start=start,
                end=end, keywords=SCOPE)


    def test_valid_facebook_permalink_other_page_or_post_is_hold(self):
        start = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
        fake = api("https://graph.facebook.com/v26.0/"
                   + FBPAGE + "/published_posts", "mock",
                   expected_host="graph.facebook.com")["data"][0]
        from rasd_social_official_intake import _fb_post
        for url in (
            "https://www.facebook.com/999999999/posts/456789012",
            f"https://www.facebook.com/{FBPAGE}/posts/111111111",
            "https://www.facebook.com/UnknownPage/posts/456789012",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    _fb_post({**fake, "permalink_url": url},
                             {"id": FBPAGE, "name": "page"},
                             start=start, end=end, keywords=SCOPE)

    def test_facebook_missing_cursor_not_false_complete(self):
        start = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
        def without_cursor(url, token, *, expected_host):
            return {"data": [], "paging": {"next":
                    "https://graph.facebook.com/v26.0/unknown?after=hidden"}}
        result = collect_approved_facebook(
            FB, token="mock", start=start, end=end, keywords=SCOPE,
            getter=without_cursor)
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["pages_with_hold"], 1)
        self.assertEqual(result["matched_count"], 0)

    def test_social_api_partial_error_body_rejected_by_transport(self):
        from io import BytesIO
        class MockReply:
            def __init__(self, url):
                self.url = url
                self.headers = {}
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def geturl(self): return self.url
            def read(self, n):
                return b'{"data":[],"errors":[{"title":"internal"}]}'
        class MockOpener:
            def open(self, request, timeout):
                return MockReply(request.full_url)
        with self.assertRaisesRegex(RuntimeError, "error_or_partial"):
            platform_json_get(
                "https://api.x.com/2/tweets/search/recent?query=planning",
                "non-real-token", expected_host="api.x.com",
                requester=MockOpener())


    def test_instagram_evidence_bridge_to_four_word_reports_offline(self):
        conf = config()
        conf["instagram"] = {
            "approved": True, "access_confirmed": True,
            "accounts": [{"id": "17841401234567890",
                          "username": "planning.eg"}],
            "max_pages_per_account": 1, "page_size": 25,
        }
        conf["original_post_browser_capture_approved"] = True
        env = {**ENV, "RASD_INSTAGRAM_PAGE_ACCESS_TOKEN": "fake-ig-test"}
        def three_api(url, token, *, expected_host):
            if "/17841401234567890/media?" in url:
                return {"data": [{
                    "id": "18270815569115548",
                    "caption": "وزارة التخطيط تشارك تحديثات تنموية",
                    "timestamp": "2026-11-08T19:45:00+0000",
                    "username": "planning.eg",
                    "permalink": "https://www.instagram.com/p/ABC123xyz/",
                }]}
            return api(url, token, expected_host=expected_host)
        def fake_capture(row, path, *, owner_authorized):
            self.assertTrue(owner_authorized)
            c = {"facebook": "white", "x": "lightgray",
                 "instagram": "beige"}[row["platform"]]
            Image.new("RGB", (490, 280), c).save(path, "PNG")
            return {
                "status": "verified", "url": row["url"],
                "platform_post_id": row["platform_post_id"],
                "method": "authorized_platform_original_capture",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        with tempfile.TemporaryDirectory() as folder:
            result = run_no_send(
                now=NOW, final_day=date(2026, 11, 8),
                output=Path(folder) / "reports",
                probe_social=True, capture_social=True,
                social_collector=lambda **kw: collect_social(
                    live=True, now=NOW, config=conf,
                    getter=three_api, environment=env),
                social_screenshot=fake_capture,
                social_config=conf, social_environment=env)
            self.assertEqual(result["reports"]["social-hourly"]["items"], 3)
            self.assertEqual(result["reports"]["social-daily"]["items"], 0)
            self.assertEqual(len(Document(
                result["reports"]["social-hourly"]["path"]).inline_shapes), 3)
            self.assertFalse(result["email_sent"])



if __name__ == "__main__":
    unittest.main()
