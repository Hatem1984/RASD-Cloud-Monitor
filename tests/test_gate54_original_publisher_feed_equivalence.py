"""Gate54: first-party shadow RSS is NEVER approved on mere HTTPS validity.

Original live source samples in CI showed 20/20 items each but ZERO overlap,
so a production switch would silently lose original news inventory.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from publisher_rss_equivalence import (
    audit_shadow_equivalence, require_two_valid_independent_snapshots,
)

ROOT = Path(__file__).resolve().parents[1]


def sample(ids, *, date="Sun, 18 Oct 2026 10:00:00 +0300",
           altered=None, host="www.almasryalyoum.com"):
    fragments = []
    for number in ids:
        current_date = (
            "Sun, 18 Oct 2026 11:00:00 +0300"
            if altered == number else date
        )
        fragments.append(
            "<item><title>وزارة التخطيط خبر " + str(number) + "</title>"
            "<link>https://" + host + "/news/details/" + str(number) + "</link>"
            "<pubDate>" + current_date + "</pubDate></item>"
        )
    return ("<rss><channel>" + "".join(fragments) +
            "</channel></rss>").encode("utf-8")


class OriginalPublisherShadowEquivalenceTests(unittest.TestCase):
    def test_live_disjoint_twenty_vs_twenty_does_not_authorize_switch(self):
        audit = audit_shadow_equivalence(
            sample(range(1,21)), sample(range(101,121)))
        self.assertEqual(audit["primary_items"], 20)
        self.assertEqual(audit["shadow_items"], 20)
        self.assertEqual(audit["intersection"], 0)
        self.assertEqual(audit["missing_primary_items"], 20)
        self.assertFalse(audit["snapshot_no_loss"])
        self.assertFalse(audit["production_source_switch_allowed"])
        self.assertFalse(require_two_valid_independent_snapshots([audit,audit]))

    def test_identical_one_snapshot_still_not_sufficient(self):
        same = audit_shadow_equivalence(sample([4,5]), sample([4,5,6]))
        self.assertTrue(same["snapshot_no_loss"])
        self.assertFalse(same["production_source_switch_allowed"])
        self.assertFalse(require_two_valid_independent_snapshots([same]))
        self.assertTrue(require_two_valid_independent_snapshots([same,same]))

    def test_same_article_original_publisher_date_change_is_not_equivalent(self):
        bad = audit_shadow_equivalence(sample([4,5]), sample([4,5],altered=4))
        self.assertEqual(bad["changed_titles_or_original_dates"],1)
        self.assertFalse(bad["snapshot_no_loss"])

    def test_missing_original_article_blocks_substitute_even_with_more_total(self):
        bad = audit_shadow_equivalence(sample([4,5,6]),
                                      sample([4,5,7,8,9,10]))
        self.assertEqual(bad["missing_primary_items"],1)
        self.assertFalse(bad["snapshot_no_loss"])

    def test_bad_xml_unknown_publisher_and_malformed_date_never_pass(self):
        for invalid in [
            b"<rss><channel><item>bad",
            b"<!DOCTYPE rss [<!ENTITY boom SYSTEM 'file:///x'>]><rss/>",
            sample([1],host="evil.invalid"),
            sample([1],date="Sat, 18 Oct 2026 09:00:00"),
            b"<rss><channel></channel></rss>",
        ]:
            with self.subTest(invalid=invalid[:35]):
                with self.assertRaises((ET.ParseError,ValueError)):
                    audit_shadow_equivalence(sample([1]),invalid)

    def test_shadow_must_be_exact_first_party_url_never_unreviewed_host(self):
        with self.assertRaisesRegex(ValueError,"shadow_not_reviewed"):
            audit_shadow_equivalence(sample([1]),sample([1]),
                shadow_url="https://rss.thirdparty.example/masry")
        with self.assertRaisesRegex(ValueError,"primary_not_approved"):
            audit_shadow_equivalence(sample([1]),sample([1]),
                original_url="https://www.almasryalyoum.com/rss/rssfeed")

    def test_sources_json_unchanged_by_shadow_only_research(self):
        cfg=json.loads((ROOT/"sources.json").read_text(encoding="utf-8"))
        self.assertEqual([f["url"] for f in cfg["feeds"]],[
            "https://hapijournal.com/feed/",
            "https://www.almasryalyoum.com/rss/rssfeeds",
        ])
        self.assertEqual(cfg["keywords"],[
            "وزارة التخطيط","وزير التخطيط","وزيرة التخطيط",
            "التخطيط والتنمية الاقتصادية"
        ])


if __name__=="__main__":
    unittest.main()
