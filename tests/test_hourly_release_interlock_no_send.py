"""Release interlock: branch merge cannot automatically send hourly emails.

All protected GitHub/Cloudflare scheduled steps use the exact owner-controlled
variable with false fallback. HTML first-party sources stay opt-in.
"""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class HourlyReleaseInterlock(unittest.TestCase):
    def test_three_delivery_workflows_use_exact_owner_var_with_false_default(self):
        for name in (
            "rasd-scheduled.yml",
            "rasd-schedule-backup.yml",
            "rasd-cloudflare-dispatch.yml",
        ):
            with self.subTest(workflow=name):
                text=(ROOT/".github"/"workflows"/name).read_text("utf-8")
                self.assertIn(
                    "vars.RASD_HOURLY_REPORTS_ENABLED || 'false'", text)
                self.assertNotIn("RASD_HOURLY_REPORTS_ENABLED: 'true'",text)
                for gate in (
                    "RASD_DAILY_VOLUME_DELIVERY_ENABLED",
                    "RASD_CONTEXT_SCOPE_ENABLED",
                    "RASD_ALMAL_ORIGINAL_HTML_ENABLED",
                    "RASD_YOUM7_ORIGINAL_HTML_ENABLED",
                ):
                    self.assertIn("vars." + gate + " || 'false'", text)
                    self.assertNotIn(gate + ": 'true'", text)
                self.assertNotIn("RASD_YOUM7_ORIGINAL_HTML_ENABLED: 'true'",text)
                self.assertNotIn("RASD_ALMAL_ORIGINAL_HTML_ENABLED: 'true'",text)

    def test_html_publishers_are_optional_and_not_misrepresented_as_rss(self):
        inventory=json.loads(
            (ROOT/"sources_newsroom_active.json").read_text("utf-8"))
        self.assertEqual(len(inventory["feeds"]),14)
        html=inventory["original_html_sources"]
        self.assertEqual({x["id"] for x in html},
                         {"almal_html","youm7_html"})
        self.assertTrue(all(x["type"].endswith("html") for x in html))
        self.assertTrue(all(x["homepage_url"].startswith("https://")
                            for x in html))


if __name__=="__main__":
    unittest.main()
