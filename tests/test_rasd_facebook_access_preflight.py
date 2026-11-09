"""Facebook PPCA/managed Page preflight: fully mocked, NO real Meta requests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from rasd_facebook_access_preflight import (
    CONFIG_PATH, preflight, _page_samples)
from rasd_social_official_intake import collect_social


PID = "123456789"
POST = PID + "_456789012"
URL = f"https://www.facebook.com/{PID}/posts/456789012"
NOW = datetime(2026, 11, 8, 18, 20, tzinfo=timezone.utc)


def configuration(mode="public_ppca"):
    return {
        "schema_version": 1,
        "facebook": {
            "access_mode": mode, "approved": True,
            "ppca_granted": True, "access_confirmed": True,
            "pages": [{"id": PID, "name": "صفحة رصد اختبار مصطنعة"}],
            "max_pages_per_page": 2,
            "max_posts_per_page": 25,
        },
        "x": {"approved": False}, "instagram": {"approved": False},
        "linkedin": {"approved": False},
    }


def get_page(url, token, *, expected_host):
    assert expected_host == "graph.facebook.com"
    assert token == "synthetic-test-token-123"
    assert "token=" not in url and "access_token" not in url
    if url.endswith(f"/{PID}?fields=id%2Cname"):
        return {"id": PID, "name": "صفحة رصد اختبار مصطنعة"}
    if url.startswith("https://graph.facebook.com/v26.0/" + PID + "/posts") or url.startswith("https://graph.facebook.com/v26.0/" + PID + "/published_posts"):
        return {"data": [{
            "id": POST, "message": "وزارة التخطيط تناقش أهداف التنمية",
            "created_time": "2026-11-08T17:30:00+0000",
            "permalink_url": URL,
        }]}
    raise AssertionError("Unexpected original endpoint: " + url)


class FacebookPreflightQA(unittest.TestCase):
    def test_actual_repository_default_cannot_call_meta(self):
        conf = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(conf["facebook"]["access_mode"], "public_ppca")
        self.assertFalse(conf["facebook"]["approved"])
        self.assertFalse(conf["facebook"]["ppca_granted"])
        self.assertEqual(conf["facebook"]["pages"], [])
        def no_network(*args, **kwargs):
            self.fail("Unapproved Meta access must have zero network")
        result = preflight(config=conf, live=True, getter=no_network,
                           env={"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"})
        self.assertEqual(result["status"], "HOLD_NOT_APPROVED")
        self.assertEqual(result["pages_readable"], 0)
        self.assertFalse(result["smtp_sent"])

    def test_explicit_public_content_grant_is_required(self):
        conf = configuration()
        conf["facebook"]["ppca_granted"] = False
        result = preflight(
            config=conf, live=True,
            env={"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=lambda *a, **k: self.fail("PPCA not granted"))
        self.assertEqual(result["status"], "HOLD_META_ACCESS_GRANT_REQUIRED")
        self.assertEqual(result["pages_readable"], 0)

    def test_missing_token_and_wrong_token_type_hold(self):
        conf = configuration()
        for env in ({}, {"RASD_META_PAGE_ACCESS_TOKEN":"synthetic-test-token-123"}):
            result = preflight(config=conf, live=True, env=env,
                               getter=lambda *a, **k: self.fail("No PPCA token"))
            self.assertEqual(result["status"], "HOLD_META_TOKEN_NOT_CONFIGURED")

    def test_live_readonly_preflight_can_verify_approved_page_metadata(self):
        conf = configuration()
        env = {"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"}
        got = preflight(config=conf, live=True, env=env, getter=get_page)
        self.assertEqual(got["status"], "API_METADATA_READABLE_NOT_IMAGE_PROOF")
        self.assertEqual(got["pages_readable"], 1)
        self.assertEqual(got["page_results"][0]["sample_posts_checked"], 1)
        self.assertEqual(got["page_results"][0]["endpoint_edge"], "posts")
        self.assertEqual(got["original_images_verified"], 0)
        self.assertNotIn("synthetic-test-token", json.dumps(got))
        self.assertNotIn("وزارة التخطيط", json.dumps(got))

    def test_wrong_page_or_post_permalink_never_passes(self):
        def other_page(url, token, *, expected_host):
            got = get_page(url, token, expected_host=expected_host)
            if "data" in got:
                got["data"][0]["permalink_url"] = (
                    "https://www.facebook.com/999999999/posts/456789012")
            return got
        result = preflight(
            config=configuration(), live=True,
            env={"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=other_page)
        self.assertEqual(result["status"], "PARTIAL_META_ACCESS_HOLD")
        self.assertEqual(result["pages_held"], 1)
        self.assertEqual(result["original_images_verified"], 0)

    def test_empty_readable_api_sample_is_not_coverage_proof(self):
        def empty_posts(url, token, *, expected_host):
            got = get_page(url, token, expected_host=expected_host)
            if "data" in got:
                got["data"] = []
            return got
        result = preflight(
            config=configuration(), live=True,
            env={"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=empty_posts)
        self.assertEqual(result["pages_readable"], 1)
        self.assertEqual(result["page_results"][0]["sample_posts_checked"], 0)
        self.assertEqual(result["original_images_verified"], 0)

    def test_managed_page_uses_distinct_page_token(self):
        conf = configuration(mode="managed_page")
        result = preflight(
            config=conf, live=True,
            env={"RASD_META_PAGE_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=get_page)
        self.assertEqual(result["pages_readable"], 1)
        self.assertEqual(result["page_results"][0]["endpoint_edge"],
                         "published_posts")
        conf["facebook"]["ppca_granted"] = False
        # Managed Page token is separate from the PPCA App review grant.
        self.assertEqual(preflight(
            config=conf, live=True,
            env={"RASD_META_PAGE_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=get_page)["pages_readable"], 1)

    def test_main_collection_respects_public_mode_and_credential_gate(self):
        config = configuration()
        fb = config["facebook"]
        fb["ppca_granted"] = False
        def no_call(*args, **kwargs):
            self.fail("Public Facebook cannot run without PPCA approval")
        result = collect_social(
            live=True, config=config, now=NOW,
            environment={"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=no_call)
        self.assertEqual(result["post_candidates"], [])
        fb["ppca_granted"] = True
        def posts(url, token, *, expected_host):
            # PPCA collector requests /posts; no preflight here.
            self.assertIn(f"/{PID}/posts?", url)
            p = get_page(url, token, expected_host=expected_host)
            if "data" not in p:
                self.fail("Production collection unexpected Page id call")
            return p
        result = collect_social(
            live=True, config=config, now=NOW,
            environment={"RASD_META_PPCA_ACCESS_TOKEN":"synthetic-test-token-123"},
            getter=posts)
        self.assertEqual(len(result["post_candidates"]), 1)
        self.assertEqual(result["post_candidates"][0]["evidence_status"],
                         "HOLD_ORIGINAL_POST_SCREENSHOT")
        self.assertEqual(result["original_screenshots_verified"], 0)
        self.assertFalse(result["smtp_sent"])

    def test_page_name_must_match_owner_approved_identity(self):
        def different_name(url, token, *, expected_host):
            got = get_page(url, token, expected_host=expected_host)
            if "name" in got:
                got["name"] = "صفحة أخرى غير معتمدة"
            return got
        result = preflight(
            config=configuration(), live=True,
            env={"RASD_META_PPCA_ACCESS_TOKEN": "synthetic-test-token-123"},
            getter=different_name)
        self.assertEqual(result["pages_readable"], 0)
        self.assertEqual(result["status"], "PARTIAL_META_ACCESS_HOLD")

    def test_invalid_approved_page_id_cannot_trigger_meta_request(self):
        conf = configuration()
        conf["facebook"]["pages"][0]["id"] = "123456789?access_token=secret"
        with self.assertRaises(ValueError):
            preflight(config=conf, live=True,
                      env={"RASD_META_PPCA_ACCESS_TOKEN":
                           "synthetic-test-token-123"},
                      getter=lambda *a, **k: self.fail("Bad page ID"))


    def test_ppca_and_managed_preflight_do_not_mix_edges(self):
        for mode, edge, secret_key in (
            ("public_ppca", "/posts?", "RASD_META_PPCA_ACCESS_TOKEN"),
            ("managed_page", "/published_posts?", "RASD_META_PAGE_ACCESS_TOKEN"),
        ):
            with self.subTest(mode=mode):
                paths = []
                def checked(url, token, *, expected_host):
                    if "/posts?" in url or "/published_posts?" in url:
                        paths.append(url)
                        self.assertIn(edge, url)
                    return get_page(url, token, expected_host=expected_host)
                report = preflight(config=configuration(mode), live=True,
                    env={secret_key: "synthetic-test-token-123"},
                    getter=checked)
                self.assertEqual(report["pages_readable"], 1)
                self.assertEqual(len(paths), 1)
                self.assertEqual(report["original_images_verified"], 0)

    def test_unverified_public_app_must_never_read_even_with_token(self):
        conf = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(conf["facebook"]["approved"], False)
        self.assertEqual(conf["facebook"]["ppca_granted"], False)
        self.assertEqual(conf["facebook"]["pages"], [])
        result = preflight(config=conf, live=True,
            env={"RASD_META_PPCA_ACCESS_TOKEN": "fake-token-for-qa"},
            getter=lambda *a, **k: self.fail("Unapproved app made network call"))
        self.assertEqual(result["status"], "HOLD_NOT_APPROVED")
        self.assertFalse(result["smtp_sent"])


if __name__ == "__main__":
    unittest.main()
