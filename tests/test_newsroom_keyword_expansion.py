"""Owner-approved Planning expansion without enabling unreliable publisher RSS."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from monitor import parse_rss, read_feed

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
ACTIVE=json.loads((ROOT/"sources_newsroom_active.json").read_text(encoding="utf-8"))
CANDIDATES=json.loads((ROOT/"sources_newsroom_expansion_candidates.json").read_text(encoding="utf-8"))
HAPI=ACTIVE["feeds"][0]


def xml(headline, summary="", date="Sun, 25 Oct 2026 11:00:00 +0000",
        host="https://hapijournal.com/news/planning-verified"):
    return (
        '<rss version="2.0"><channel><item><title>'
        + headline + '</title><link>' + host
        + '</link><description>' + summary
        + '</description><pubDate>' + date
        + '</pubDate></item></channel></rss>'
    ).encode("utf-8")


class MinistryExpansionRelease(unittest.TestCase):
    def test_18_specific_keywords_have_no_duplicate_and_preserve_original(self):
        base=json.loads((ROOT/"sources.json").read_text("utf-8"))
        self.assertEqual(len(ACTIVE["keywords"]),18)
        self.assertEqual(len(set(ACTIVE["keywords"])),18)
        self.assertEqual(ACTIVE["keywords"][:len(base["keywords"])],
                         base["keywords"])
        for p in ("المعهد القومي للتخطيط","خطة التنمية الاقتصادية والاجتماعية",
                  "الخطة الاستثمارية للدولة","البرنامج الوطني للإصلاحات الهيكلية"):
            self.assertIn(p,ACTIVE["keywords"])

    def test_expansion_matches_official_topic_in_headline(self):
        for title in (
          "المعهد القومي للتخطيط يبحث خطط العام",
          "برنامج حول الخطة الاستثمارية للدولة",
          "مستهدفات خطة التنمية الاقتصادية والاجتماعية لعام 2027",
          "البرنامج الوطني للإصلاحات الهيكلية يدخل مرحلة جديدة",
          "وزارة التخطيط والتنمية الاقتصادية تستعرض برنامجًا جديدًا",
        ):
            with self.subTest(title=title):
                cnt,matching=parse_rss(
                    xml(title),HAPI,ACTIVE["keywords"],NOW,
                    require_complete_items=True)
                self.assertEqual((cnt,len(matching)),(1,1))
                self.assertEqual(matching[0]["match_origin"],"title")

    def test_expanded_topic_in_description_with_real_date(self):
        count,match=parse_rss(
            xml("اجتماع اقتصادي جديد",
                "تقرير عن الخطة العامة للتنمية الاقتصادية والاجتماعية"),
            HAPI,ACTIVE["keywords"],NOW,require_complete_items=True)
        self.assertEqual((count,len(match)),(1,1))
        self.assertEqual(match[0]["match_origin"],"publisher_description")

    def test_unrelated_economy_and_sports_do_not_match(self):
        for text in (
            "تنمية الإيرادات في قطاع البنوك",
            "وزير المالية يبحث زيادة الإنفاق",
            "أزمة التخطيط للمباراة",
            "رؤية مصر 2030 تعود في احتفال شعبي",
            "تعزيز العلاقات مع التعاون الدولي فقط",
        ):
            with self.subTest(text=text):
                cnt,news=parse_rss(xml(text),HAPI,ACTIVE["keywords"],NOW,
                                   require_complete_items=True)
                self.assertEqual((cnt,len(news)),(1,0))

    def test_all_new_publisher_candidates_are_on_hold_not_in_mail(self):
        ids=[x["id"] for x in ACTIVE["feeds"]]
        self.assertEqual(ids,["hapi","almasryalyoum","shorouk","alborsa"])
        self.assertEqual(CANDIDATES["policy"],
                         "research_only_not_active_feed_not_in_gmail_delivery")
        self.assertEqual(len(CANDIDATES["candidates"]),4)
        for item in CANDIDATES["candidates"]:
            self.assertNotIn(item["id"],ids)
            self.assertTrue(item["status"].startswith(("HOLD_","QA_ONLY_")))
            self.assertTrue(item["acceptance_gate"])

    def test_masrawy_bad_original_date_cannot_be_invented(self):
        # Exact native RSS date example observed from the original publisher
        # lacks timezone: "10/25/2026 6:21:45 PM".
        cfg=dict(HAPI,allowed_article_hosts=["www.masrawy.com"])
        feed=xml("وزارة التخطيط",date="10/25/2026 6:21:45 PM",
                 host="https://www.masrawy.com/news/news_egypt/details/1")
        with self.assertRaisesRegex(ValueError,
                                    "rss_original_item_date_unverifiable"):
            parse_rss(feed,cfg,ACTIVE["keywords"],NOW,
                      require_complete_items=True)

    def test_held_publisher_rss_endpoint_is_not_even_fetch_allowlisted(self):
        for row in CANDIDATES["candidates"]:
            url=row.get("feed_url")
            if not url:continue
            with self.assertRaisesRegex(ValueError,"feed_endpoint_not_reviewed"):
                read_feed(url,10_000)

    def test_no_second_send_mode_or_credentials_in_candidate_registry(self):
        raw=(ROOT/"sources_newsroom_expansion_candidates.json").read_text("utf-8")
        for forbidden in ("RASD_GMAIL_APP_PASSWORD","private_key",
                          "approved_recipient","smtp_sent","secret_token"):
            self.assertNotIn(forbidden,raw)


if __name__=="__main__":
    unittest.main()
