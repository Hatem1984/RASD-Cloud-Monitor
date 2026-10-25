"""Source expansion: precise planning terms and Masrawy source-owned timezone.

Offline-only; all webpage fetchers injected/mocked. Zero Gmail, no secrets.
"""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from capture_public import allowed_url
from masrawy_original_date import (original_pubdate, fetch_original_page)
from monitor import parse_rss, read_feed

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026, 10, 25, 16, tzinfo=timezone.utc)
ACTIVE=json.loads((ROOT/"sources_newsroom_active.json").read_text(encoding="utf-8"))
CANDIDATES=json.loads((ROOT/"sources_newsroom_expansion_candidates.json").read_text(encoding="utf-8"))
HAPI=ACTIVE["feeds"][0]
MASRAWY=next(x for x in ACTIVE["feeds"] if x["id"]=="masrawy")
LINK="https://www.masrawy.com/news/news_egypt/details/2026/10/25/123/valid"
TITLE="وزارة التخطيط تستعرض الخطة الاستثمارية للدولة"
DATE="10/25/2026 6:21:45 PM"
ISO="2026-10-25T18:21:45+03:00"


def xml(headline, summary="",date="Sun, 25 Oct 2026 11:00:00 +0000",
        host="https://hapijournal.com/planning-news"):
    return (
        '<rss version="2.0"><channel><item><title>' + headline
        + '</title><link>' + host
        + '</link><description>' + summary
        + '</description><pubDate>' + date
        + '</pubDate></item></channel></rss>'
    ).encode("utf-8")


def publisher_jsonld(headline=TITLE, date=ISO):
    payload=json.dumps({"@type":"NewsArticle","headline":headline,
                        "datePublished":date},ensure_ascii=False)
    return ('<!doctype html><html><head><script type="application/ld+json">'
            +payload+'</script></head></html>').encode("utf-8")


class MinistryExpansionRelease(unittest.TestCase):
    def test_29_distinct_phrases_and_14_production_publisher_profiles(self):
        base=json.loads((ROOT/"sources.json").read_text("utf-8"))
        self.assertEqual(len(ACTIVE["keywords"]),29)
        self.assertEqual(len(set(ACTIVE["keywords"])),29)
        self.assertEqual(ACTIVE["keywords"][:len(base["keywords"])],
                         base["keywords"])
        self.assertEqual([x["id"] for x in ACTIVE["feeds"]],
                         ["hapi","almasryalyoum","shorouk","alborsa","masrawy"]+['almessa', 'elbalad', 'vetogate', 'dailynewsegypt', 'egyptindependent', 'enterpriseam', 'egyptianstreets', 'skynewsarabia', 'inp_official'])
        for phrase in ("المعهد القومي للتخطيط",
                       "خطة التنمية الاقتصادية والاجتماعية",
                       "الخطة الاستثمارية للدولة",
                       "البرنامج الوطني للإصلاحات الهيكلية"):
            self.assertIn(phrase,ACTIVE["keywords"])

    def test_new_terms_are_relevant_in_title_and_description(self):
        for title in (
          "المعهد القومي للتخطيط يبحث خطط العام",
          "برنامج حول الخطة الاستثمارية للدولة",
          "مستهدفات خطة التنمية الاقتصادية والاجتماعية لعام 2027",
          "البرنامج الوطني للإصلاحات الهيكلية يدخل مرحلة جديدة",
        ):
            with self.subTest(title=title):
                count,found=parse_rss(
                    xml(title),HAPI,ACTIVE["keywords"],NOW,
                    require_complete_items=True)
                self.assertEqual((count,len(found)),(1,1))
        count,found=parse_rss(
            xml("اجتماع اقتصادي جديد",
                "تقرير عن الخطة العامة للتنمية الاقتصادية والاجتماعية"),
            HAPI,ACTIVE["keywords"],NOW,require_complete_items=True)
        self.assertEqual((count,len(found)),(1,1))
        self.assertEqual(found[0]["match_origin"],"publisher_description")

    def test_unrelated_economy_and_sports_stay_out(self):
        for title in ("تنمية الإيرادات في قطاع البنوك",
                      "وزير المالية يبحث زيادة الإنفاق",
                      "أزمة التخطيط للمباراة",
                      "رؤية مصر 2030 تعود في احتفال شعبي"):
            with self.subTest(title=title):
                c,found=parse_rss(xml(title),HAPI,ACTIVE["keywords"],NOW,
                                  require_complete_items=True)
                self.assertEqual((c,len(found)),(1,0))

    def test_original_page_newsarticle_explicit_timezone_confirms_rss_clock(self):
        dt,pub=original_pubdate(LINK,TITLE,DATE,
                                fetch=lambda _:publisher_jsonld())
        self.assertEqual(dt.isoformat(),ISO)
        self.assertIn("+0300",pub)

    def test_rss_masrawy_strict_integration_uses_verification_once_per_item(self):
        dt,pub=original_pubdate(LINK,TITLE,DATE,
                                fetch=lambda _:publisher_jsonld())
        with patch("masrawy_original_date.original_pubdate",
                   return_value=(dt,pub)) as origin:
            count,found=parse_rss(
                xml(TITLE,date=DATE,host=LINK),MASRAWY,
                ACTIVE["keywords"],NOW,require_complete_items=True)
        self.assertEqual((count,len(found)),(1,1))
        self.assertEqual(origin.call_count,1)
        self.assertEqual(found[0]["published"],pub)
        self.assertTrue(allowed_url(LINK,"masrawy.com"))

    def test_wrong_local_clock_causes_total_rejection_no_guessed_timezone(self):
        with self.assertRaisesRegex(ValueError,
                                    "masrawy_publisher_publication_date_unverified"):
            original_pubdate(LINK,TITLE,DATE,
                             fetch=lambda _:publisher_jsonld(
                                 date="2026-10-25T17:21:45+03:00"))

    def test_publisher_headline_mismatch_always_rejected(self):
        with self.assertRaisesRegex(ValueError,
                                    "masrawy_publisher_publication_date_unverified"):
            original_pubdate(LINK,TITLE,DATE,
                             fetch=lambda _:publisher_jsonld(
                                headline="خبر اقتصادي مختلف"))

    def test_unzoned_publisher_jsonld_does_not_rescue_naive_rss(self):
        with self.assertRaisesRegex(ValueError,
                                    "masrawy_publisher_publication_date_unverified"):
            original_pubdate(LINK,TITLE,DATE,
                             fetch=lambda _:publisher_jsonld(
                                 date="2026-10-25T18:21:45"))

    def test_reject_unsafe_lookalike_article_host_before_network(self):
        with self.assertRaisesRegex(ValueError,"masrawy_original_url_not_approved"):
            fetch_original_page("https://www.masrawy.com.evil.invalid/news/x")
        with self.assertRaisesRegex(ValueError,"masrawy_original_url_not_approved"):
            fetch_original_page("http://www.masrawy.com/news/x")
        with self.assertRaisesRegex(ValueError,"masrawy_original_url_not_approved"):
            fetch_original_page("https://www.masrawy.com:8080/news/x")

    def test_other_three_candidate_sources_remain_on_hold(self):
        active={x["id"] for x in ACTIVE["feeds"]}
        review={x["id"]:x for x in CANDIDATES["candidates"]}
        self.assertTrue(review["masrawy"]["status"].startswith("ACTIVATED_"))
        self.assertEqual(len(review),9)
        for name in ("youm7_reports","youm7_politics","mped_official","almal","elwatan","cairo24","ahram_gate","akhbarelyom"):
            self.assertNotIn(name,active)
            self.assertTrue(review[name]["status"].startswith(("HOLD_","QA_ONLY_")))

    def test_unapproved_youm7_feed_not_allowed_even_with_valid_rss(self):
        with self.assertRaisesRegex(ValueError,"feed_endpoint_not_reviewed"):
            read_feed(CANDIDATES["candidates"][1]["feed_url"],10000)

    def test_verified_ministry_programme_keywords_expand_discovery_without_generic_economy(self):
        # Phrases confirmed on official Egyptian Ministry of Planning pages.
        # These are exact publisher headline/description matches, NOT open-ended
        # economic-sector words that could silently dilute ministry coverage.
        phrases = [
            "البرنامج الوطني للتحول الاقتصادي",
            "السردية الوطنية للتنمية الاقتصادية",
            "المبادرة الوطنية للمشروعات الخضراء الذكية",
            "المراجعة الوطنية الطوعية لمصر",
            "تقرير مصر الوطني الطوعي",
            "المنظومة المتكاملة للتخطيط التنموي",
        ]
        for phrase in phrases:
            self.assertIn(phrase, ACTIVE["keywords"])
            count, found = parse_rss(
                xml("تطورات " + phrase), HAPI, ACTIVE["keywords"], NOW,
                require_complete_items=True)
            self.assertEqual((count,len(found)), (1,1), phrase)
        for unrelated in ("النمو الاقتصادي يواصل الصعود",
                          "الاستثمار الأجنبي في أسواق المال",
                          "تقرير التنمية المستدامة في دولة أخرى"):
            count, found = parse_rss(xml(unrelated), HAPI, ACTIVE["keywords"],
                                     NOW, require_complete_items=True)
            self.assertEqual((count,len(found)), (1,0), unrelated)

    def test_five_new_candidate_newsrooms_are_not_activated_without_native_rss(self):
        for ident in ("almal","elwatan","cairo24","ahram_gate","akhbarelyom"):
            candidate = next(x for x in CANDIDATES["candidates"] if x["id"]==ident)
            self.assertTrue(candidate["status"].startswith("HOLD_"))
            self.assertNotIn(ident, {x["id"] for x in ACTIVE["feeds"]})
            self.assertTrue(candidate["page_url"].startswith("https://"))

    def test_no_secrets_credentials_or_gmail_in_new_module(self):
        raw=(ROOT/"masrawy_original_date.py").read_text("utf-8")
        for bad in ("RASD_GMAIL_APP_PASSWORD","PrivateGitHubLedger",
                    "smtplib","send_message(","GITHUB_TOKEN"):
            self.assertNotIn(bad,raw)


if __name__=="__main__":
    unittest.main()
