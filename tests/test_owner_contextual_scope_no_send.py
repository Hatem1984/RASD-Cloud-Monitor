"""Owner-approved Ministry scope widening without unrelated economic noise.

Zero network, no artificial publisher proof, no SMTP and no live source
activation. Original RSS date/host/image gates remain unchanged.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from monitor import inspect, parse_rss
from rasd_relevance_scope import (
    contextual_title_matches, scope_active, SCOPE_VERSION)

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/"sources_newsroom_active.json").read_text("utf-8"))
FEED=next(x for x in CONFIG["feeds"] if x["id"]=="hapi")
NOW=datetime(2026,11,21,16,0,tzinfo=timezone.utc)
DATE="Sat, 21 Nov 2026 13:32:00 +0000"


def xml(title,excerpt="",dated=DATE,host="hapijournal.com"):
    import xml.sax.saxutils as xml_safe
    esc=xml_safe.escape
    return (
        '<rss version="2.0"><channel><item>'
        '<title>'+esc(title)+'</title>'
        '<link>https://'+host+'/2026/11/21/test-planning-event-8239</link>'
        '<description>'+esc(excerpt)+'</description>'
        '<pubDate>'+esc(dated)+'</pubDate>'
        '</item></channel></rss>'
    ).encode()


class EgyptPlanningContextualScopeNoSend(unittest.TestCase):
    def test_owner_context_scope_has_explicit_off_switch(self):
        self.assertEqual(CONFIG["context_scope"],SCOPE_VERSION)
        with patch.dict("os.environ",{"RASD_CONTEXT_SCOPE_ENABLED":"false"}):
            self.assertFalse(scope_active(CONFIG))
            count,matched=parse_rss(xml(
                "19 مليار جنيه استثمارات عامة لمحافظة السويس"),FEED,
                CONFIG["keywords"],NOW,require_complete_items=True)
            self.assertEqual((count,len(matched)),(1,0))
        with patch.dict("os.environ",{"RASD_CONTEXT_SCOPE_ENABLED":"true"}):
            self.assertTrue(scope_active(CONFIG))
        unreviewed=dict(CONFIG,context_scope="untrusted")
        with patch.dict("os.environ",{"RASD_CONTEXT_SCOPE_ENABLED":"true"}):
            self.assertFalse(scope_active(unreviewed))

    def test_genuine_egypt_planning_topics_can_be_discovered_without_ministry_name(self):
        relevant=[
            "19 مليار جنيه استثمارات عامة بمحافظة السويس للعام المالي 2026",
            "تطوير مشروعات البنية التحتية في القاهرة ضمن برنامج جديد",
            "مصر تعلن مستهدفات النمو الاقتصادي العام المقبل",
            "مشروعات تنموية جديدة في بورسعيد",
            "تنمية المحافظات المصرية ضمن خطة الموازنة العامة",
        ]
        for headline in relevant:
            with self.subTest(title=headline):
                self.assertTrue(contextual_title_matches(headline))
                count,found=parse_rss(xml(headline),FEED,CONFIG["keywords"],
                                       NOW,require_complete_items=True,
                                       expanded_scope=True)
                self.assertEqual((count,len(found)),(1,1))
                self.assertEqual(found[0]["match_origin"],
                                 "contextual_topic_title")
                self.assertEqual(found[0]["source"],FEED["name"])
                self.assertTrue(found[0]["published"].endswith("+0000"))

    def test_foreign_or_unrelated_news_cannot_be_used_to_fill_hourly_quota(self):
        excluded=[
            "الحكومة السعودية تعلن استثمارات عامة جديدة",
            "استثمارات عامة في المملكة العربية السعودية",
            "البنوك المصرية تعلن خطط تنمية الإيرادات",
            "فريق الكرة يعلن خطة استثمار في القاهرة",
            "القاهرة تستقبل بطولة كرة قدم عالمية",
            "شركة تكنولوجيا أمريكية تعلن نمو مبيعاتها",
            "مصر تشهد افتتاح معرض سياحي جديد",
            "مشروعات تنموية في دبي تدخل مرحلة التشغيل",
            "الحكومة الأجنبية تعلن إنفاقًا استثماريًا",
        ]
        for headline in excluded:
            with self.subTest(title=headline):
                self.assertFalse(contextual_title_matches(headline))
                count,found=parse_rss(xml(headline),FEED,CONFIG["keywords"],
                                       NOW,require_complete_items=True,
                                       expanded_scope=True)
                self.assertEqual((count,len(found)),(1,0))

    def test_original_publisher_description_may_confirm_egypt_but_not_topic(self):
        title="إعلان استثمارات عامة جديدة في العام المالي"
        self.assertTrue(contextual_title_matches(
            title,"صرحت محافظة السويس بتفاصيل الاعتماد"))
        self.assertFalse(contextual_title_matches(
            "افتتاح معرض سياحي",
            "وزارة المالية في مصر تعلن استثمارات عامة"))
        count,found=parse_rss(xml(
            title,"مشروعات في محافظة السويس"),FEED,CONFIG["keywords"],
            NOW,require_complete_items=True,expanded_scope=True)
        self.assertEqual((count,len(found)),(1,1))

    def test_owner_scope_preserves_strict_original_link_date_and_image_gates(self):
        title="مصر تعلن مستهدفات النمو الاقتصادي"
        with self.assertRaisesRegex(ValueError,
                                    "rss_original_item_date_unverifiable"):
            parse_rss(xml(title,dated="21 نوفمبر الساعة 2"),FEED,
                      CONFIG["keywords"],NOW,require_complete_items=True,
                      expanded_scope=True)
        with self.assertRaisesRegex(ValueError,
                                    "rss_original_item_identity_unverifiable"):
            parse_rss(xml(title,host="news-bad.example"),FEED,
                      CONFIG["keywords"],NOW,require_complete_items=True,
                      expanded_scope=True)
        count,found=parse_rss(
            xml(title,dated="Sat, 21 Nov 2026 15:32:00 +0000"),FEED,
            CONFIG["keywords"],NOW,require_complete_items=True,
            expanded_scope=True)
        self.assertEqual((count,len(found)),(1,1))
        self.assertNotIn("evidence_image_path",found[0])

    def test_actual_inspect_requires_both_environment_flag_and_config_scope(self):
        title="استثمارات عامة جديدة في بورسعيد"
        data=xml(title)
        no_context=dict(CONFIG,feeds=[FEED],max_feed_bytes=1500000,
                        recent_hours=72)
        with patch.dict("os.environ",{"RASD_CONTEXT_SCOPE_ENABLED":"false"}):
            plain=inspect(no_context,fetch=lambda *a:data,
                          now=NOW,article_limit=200,
                          require_complete_items=True)
        self.assertEqual(plain["matched_public_articles"],[])
        with patch.dict("os.environ",{"RASD_CONTEXT_SCOPE_ENABLED":"true"}):
            broadened=inspect(no_context,fetch=lambda *a:data,
                              now=NOW,article_limit=200,
                              require_complete_items=True)
        self.assertEqual(len(broadened["matched_public_articles"]),1)
        self.assertEqual(broadened["contextual_topic_matches_unverified_images"],1)
        self.assertTrue(broadened["owner_context_scope_enabled"])
        self.assertFalse(broadened["email_sent"])
        self.assertFalse(broadened["state_persistence_enabled"])


if __name__=="__main__":
    unittest.main()
