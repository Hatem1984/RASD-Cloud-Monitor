"""Gate69: source reliability is observation, never production approval.

No network, credentials or file writes in tests. Exactly same three
published original source IDs, empty native RSS can still be healthy.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from gate69_source_health_readonly import (
    evaluate_window, public_live_probe, validate_daily_sample,
)


def day_sample(day: date, *, bad=None, code=11):
    return {
        "day": day.isoformat(),
        "sources": [
            {"id": x, "ok": x != bad,
             "original_links": 0 if x == bad else
                              (1 if x == "mped-official" else 0),
             "xml_error_code": code if x == bad and
                                   x == "almasryalyoum" else None}
            for x in ["hapi", "almasryalyoum", "mped-official"]
        ]
    }


TODAY = date(2026, 10, 20)


class SourceReliabilityTests(unittest.TestCase):
    def test_one_genuine_complete_day_is_not_stability(self):
        result = evaluate_window([day_sample(TODAY-timedelta(days=1))],
                                 today_cairo=TODAY)
        self.assertEqual(result["status"],
                         "INSUFFICIENT_CONSECUTIVE_COMPLETED_DAYS")
        self.assertFalse(result["all_7_samples_healthy"])
        self.assertFalse(result["gmail_enabled"])
        self.assertFalse(result["r2_enabled"])

    def test_seven_distinct_consecutive_healthy_completed_days(self):
        days = [day_sample(TODAY - timedelta(days=i))
                for i in range(7, 0, -1)]
        out = evaluate_window(days, today_cairo=TODAY)
        self.assertEqual(
            out["status"],
            "OBSERVED_HEALTHY_7_DISTINCT_DAYS_NOT_UPSTREAM_GUARANTEE")
        self.assertTrue(out["all_7_samples_healthy"])
        self.assertFalse(out["production_approved"])

    def test_one_interleaved_malformed_xml_prevents_health_certificate(self):
        days = [day_sample(TODAY - timedelta(days=i),
                           bad="almasryalyoum" if i == 3 else None)
                for i in range(7, 0, -1)]
        out = evaluate_window(days, today_cairo=TODAY)
        self.assertEqual(out["status"], "HOLD_UPSTREAM_SOURCE")
        self.assertFalse(out["all_7_samples_healthy"])
        self.assertEqual(out["source_fail_days"],
                         [(TODAY-timedelta(days=3)).isoformat()])

    def test_healthy_zero_entries_original_rss_is_not_outage(self):
        s=day_sample(TODAY-timedelta(days=1))
        verified=validate_daily_sample(s,today_cairo=TODAY)
        self.assertTrue(verified["all_sources_healthy"])
        self.assertEqual(verified["source_health"][0]["original_links"],0)

    def test_missing_calendar_date_not_seven_day_uptime(self):
        dates=[TODAY-timedelta(days=i) for i in (8,7,6,4,3,2,1)]
        out=evaluate_window([day_sample(d) for d in dates],today_cairo=TODAY)
        self.assertEqual(out["status"],
                         "INSUFFICIENT_CONSECUTIVE_COMPLETED_DAYS")

    def test_duplicate_same_day_is_rejected(self):
        s=day_sample(TODAY-timedelta(days=1))
        with self.assertRaisesRegex(ValueError,"duplicate_completed_day"):
            evaluate_window([s,s],today_cairo=TODAY)

    def test_today_or_future_not_a_completed_day(self):
        for offset in (0,1,30):
            with self.assertRaisesRegex(ValueError,
                                        "requires_completed_cairo_day"):
                validate_daily_sample(day_sample(TODAY+timedelta(days=offset)),
                                      today_cairo=TODAY)

    def test_missing_extra_or_forged_sources_cannot_be_counted(self):
        day=TODAY-timedelta(days=1)
        for broken in [
            day_sample(day) | {"sources": day_sample(day)["sources"][:2]},
            day_sample(day) | {"sources": [
                *day_sample(day)["sources"][:2],
                dict(day_sample(day)["sources"][-1],id="shorouk")]},
            day_sample(day) | {"sources": [
                *day_sample(day)["sources"][:2],
                dict(day_sample(day)["sources"][-1],id="hapi")]},
        ]:
            with self.assertRaisesRegex(ValueError,"source_ids_invalid"):
                validate_daily_sample(broken,today_cairo=TODAY)

    def test_failed_source_cannot_claim_verified_links(self):
        sample=day_sample(TODAY-timedelta(days=1),bad="almasryalyoum")
        sample["sources"][1]["original_links"]=10
        with self.assertRaisesRegex(ValueError,"failed_source_claimed"):
            validate_daily_sample(sample,today_cairo=TODAY)

    def test_xml_error_code_must_be_bounded_and_fail_healthy(self):
        for code in (True,-1,0,101,"11"):
            s=day_sample(TODAY-timedelta(days=1),bad="almasryalyoum")
            s["sources"][1]["xml_error_code"]=code
            with self.subTest(code=code), self.assertRaisesRegex(ValueError,"xml_diagnostic_invalid"):
                validate_daily_sample(s,today_cairo=TODAY)
        s=day_sample(TODAY-timedelta(days=1))
        s["sources"][0]["xml_error_code"]=11
        with self.assertRaisesRegex(ValueError,"healthy_rss_xml_error_conflict"):
            validate_daily_sample(s,today_cairo=TODAY)

    def test_one_source_failure_does_not_fall_back_to_cached_report(self):
        settings={"feeds":[{"id":"hapi"},{"id":"almasryalyoum"}],
                  "keywords":["وزارة التخطيط","وزير التخطيط",
                              "وزيرة التخطيط","التخطيط والتنمية الاقتصادية"]}
        inspector_result={"sources":[
            {"feed_id":"hapi","status":"ok","verified_links":10},
            {"feed_id":"almasryalyoum","status":"failed",
             "verified_links":0,"xml_error_code":11}],
             "matched_public_articles":[{"headline":"SENSITIVE ORIGINAL"}]}
        official=Mock()
        official.request.new_context.return_value=Mock()
        player=Mock()
        player.__enter__=Mock(return_value=Mock(request=official.request))
        player.__exit__=Mock(return_value=False)
        with patch("pathlib.Path.read_text",return_value=json.dumps(settings)), \
             patch("gate69_source_health_readonly.inspect",
                   return_value=inspector_result) as inspect, \
             patch("playwright.sync_api.sync_playwright",return_value=player), \
             patch("gate69_source_health_readonly.discover_official_newslist",
                   return_value=["https://mped.gov.eg/singlenews?id=7270&lang=ar"]):
            result=public_live_probe()
        self.assertEqual(result["status"],"HOLD_ORIGINAL_SOURCE_HEALTH")
        self.assertNotIn("SENSITIVE ORIGINAL",json.dumps(result))
        self.assertFalse(result["report_created"])
        inspect.assert_called_once()

    def test_new_probe_has_no_smtp_delivery_or_cron_access(self):
        content=(Path(__file__).resolve().parents[1] /
                 "gate69_source_health_readonly.py").read_text()
        for name in ("smtplib","sendmail(","send_message(",
                     "boto3","PrivateGitHubLedger","RASD_GMAIL_APP_PASSWORD"):
            self.assertNotIn(name,content)


if __name__=="__main__":
    unittest.main()
