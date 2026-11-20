"""No-send exact Youm7 publisher tag/headline/date QA."""
import unittest
from datetime import datetime,timezone
from rasd_youm7_tag_original_research import (
    TAG_URL,NEWS_PATH,allowed,discover_links,original_news,research,
    MAX_INDEX_BYTES,MAX_PAGE_BYTES)

NOW=datetime(2026,11,20,18,10,tzinfo=timezone.utc)
URL=("https://www.youm7.com/story/2026/11/20/"
     "%D9%88%D8%B2%D9%8A%D8%B1-%D8%A7%D9%84%D8%AA%D8%AE%D8%B7%D9%8A%D8%B7/7625874")
KW=["وزير التخطيط","وزارة التخطيط"]


def html_article(when="2026-11-20T13:57:27Z",
                 title="وزير التخطيط يعرض مبادرة المشروعات الخضراء"):
    return ('<html><head><meta property="article:published_time" content="'+when+
            '"></head><body><h1>'+title+'</h1></body></html>').encode()


class Youm7TagResearchNoSend(unittest.TestCase):
    def fixture(self):
        return ('<a href="'+URL+'">وزير التخطيط يعرض المبادرة</a>'
                '<a href="https://evil.example/story/2026/11/20/bad/7625875">'
                'وزير التخطيط</a>'
                '<a href="/story/2026/11/20/football/7625876">'
                'فريق الأهلي يفوز</a>').encode()

    def test_only_own_ministry_article_links_accepted(self):
        self.assertEqual(discover_links(self.fixture(),KW),[URL])
        self.assertTrue(allowed(TAG_URL))
        self.assertFalse(allowed("https://www.youm7.com.evil.com/path"))
        self.assertFalse(allowed("http://www.youm7.com/path"))
        self.assertTrue(NEWS_PATH.fullmatch("/story/2026/11/20/x/7625874"))

    def test_original_h1_with_publisher_timezone_is_required(self):
        news=original_news(URL,html_article(),KW,now=NOW)
        self.assertIn("وزير التخطيط",news["headline"])
        self.assertEqual(news["source"],"Youm7 first-party Ministry tag HTML")
        self.assertIn("+0000",news["published"])
        with self.assertRaisesRegex(ValueError,"timezone_missing"):
            original_news(URL,html_article("2026-11-20T13:57:27"),KW,now=NOW)
        with self.assertRaisesRegex(ValueError,"headline_unrelated"):
            original_news(URL,html_article(title="الكرة المصرية اليوم"),KW,now=NOW)

    def test_publisher_tag_is_not_publication_proof_by_itself(self):
        def fetcher(url,limit):
            return self.fixture() if url==TAG_URL else b"<html><h1>وزير التخطيط</h1></html>"
        result=research(now=NOW,downloader=fetcher,keywords=KW)
        self.assertEqual(result["ministry_tag_first_party_links"],1)
        self.assertEqual(result["original_pages_dated"],0)
        self.assertEqual(result["original_page_hold"],1)
        self.assertFalse(result["smtp_sent"])
        self.assertFalse(result["production_activated"])

    def test_bounded_first_party_article_discovery_after_original_date(self):
        def fetcher(url,limit):
            self.assertIn(limit,(MAX_INDEX_BYTES,MAX_PAGE_BYTES))
            return self.fixture() if url==TAG_URL else html_article()
        result=research(now=NOW,downloader=fetcher,keywords=KW)
        self.assertEqual(result["original_pages_dated"],1)
        self.assertEqual(len(result["stories"]),1)
        self.assertEqual(result["original_page_hold"],0)


if __name__=="__main__":
    unittest.main()
