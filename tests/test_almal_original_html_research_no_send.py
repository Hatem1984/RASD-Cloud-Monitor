"""No-network strict HTML date/host original publisher QA."""
import unittest
from datetime import datetime,timezone

from rasd_almal_original_html_research import (
    ALMAL_ORIGIN,candidate_links,original_story,permitted,MAX_INDEX_BYTES,
    MAX_PAGE_BYTES,research)

NOW=datetime(2026,11,20,18,30,tzinfo=timezone.utc)
KW=["وزارة التخطيط", "وزير التخطيط"]
ARTICLE="https://almalnews.com/2148532/news-about-planning/"


def article(date="2026-11-20T17:01:20+02:00",title="وزير التخطيط يبحث مشروع بورسعيد"):
    return ('<html><head><meta property="article:published_time" '
            'content="'+date+'"></head><body><h1>'+title+
            '</h1></body></html>').encode()


class AlmalOriginalHtmlQA(unittest.TestCase):
    def test_relevant_article_link_discovery_same_first_party_only(self):
        home=('<a href="/2148532/news-about-planning/">'
              'وزير التخطيط يبحث مشروع بورسعيد</a>'
              '<a href="https://evil.example/2148532/">وزير التخطيط</a>'
              '<a href="/Home/Index/">وزير التخطيط</a>'
              '<a href="/2148533/football/">النادي يفوز بالمباراة</a>').encode()
        self.assertEqual(candidate_links(home,KW),[ARTICLE])
        self.assertFalse(permitted("https://almalnews.com.evil.example/path"))
        self.assertFalse(permitted("http://almalnews.com/2148532"))
        self.assertTrue(permitted(ALMAL_ORIGIN))

    def test_original_first_party_article_time_title_and_id(self):
        item=original_story(ARTICLE,article(),KW,now=NOW)
        self.assertIn("وزير التخطيط",item["headline"])
        self.assertIn("+0200",item["published"])
        self.assertEqual(item["source"],"Al Mal native publisher HTML")
        self.assertTrue(item["id"])
        with self.assertRaisesRegex(ValueError,"timezone_missing"):
            original_story(ARTICLE,article(date="2026-11-20T17:01:20"),KW,now=NOW)
        with self.assertRaisesRegex(ValueError,"headline_unrelated"):
            original_story(ARTICLE,article(title="مباراة كرة قدم"),KW,now=NOW)
        with self.assertRaisesRegex(ValueError,"outside_window"):
            original_story(ARTICLE,article(date="2026-11-10T17:01:20+02:00"),KW,now=NOW)

    def test_no_original_article_date_no_approved_story(self):
        without = '<html><h1>وزير التخطيط يبحث مشروع بورسعيد</h1></html>'.encode()
        with self.assertRaisesRegex(ValueError,"published_meta_missing"):
            original_story(ARTICLE,without,KW,now=NOW)

    def test_research_stays_read_only_and_distinguishes_hold(self):
        index=('<a href="/2148532/news-about-planning/">'
               'وزير التخطيط يبحث مشروع بورسعيد</a>').encode()
        attempted=[]
        def fetch(url,maximum):
            attempted.append((url,maximum))
            return index if url==ALMAL_ORIGIN else article()
        result=research(now=NOW,fetch=fetch)
        self.assertEqual(result["index_candidates"],1)
        self.assertEqual(result["original_page_verified"],1)
        self.assertFalse(result["production_activated"])
        self.assertFalse(result["smtp_sent"])
        self.assertEqual(attempted[0],(ALMAL_ORIGIN,MAX_INDEX_BYTES))
        self.assertEqual(attempted[1],(ARTICLE,MAX_PAGE_BYTES))

if __name__=="__main__":
    unittest.main()
