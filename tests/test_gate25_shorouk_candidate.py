"""Gate 25 native publisher candidate: offline provenance and no invented news."""
import unittest
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from gate25_shorouk_candidate import extract_candidates, publisher_article
NOW=datetime(2026,10,15,14,30,tzinfo=timezone.utc)
URL="https://www.shorouknews.com/news/view.aspx?cdate=15102026&id=91362f75-9c72-4897-a136-eb54030ffdcb"
TITLE="نائب رئيس البنك الدولي يشيد بمؤشرات الاقتصاد المصري"
DESC="عقد وزير التخطيط أحمد رستم اجتماعا لبحث التعاون مع البنك الدولي."


def feed(items):
    return ('<?xml version="1.0"?><rss><channel>'+''.join(
        f'<item><title>{escape(t)}</title><link>{escape(u)}</link>'
        f'<description>{escape(d)}</description><pubDate>{p}</pubDate></item>'
        for t,u,d,p in items
    )+'</channel></rss>').encode('utf-8')


class ShoroukCandidateTests(unittest.TestCase):
    def test_only_original_https_article_with_exact_link_structure(self):
        self.assertTrue(publisher_article(URL))
        for wrong in [
            "http://www.shorouknews.com/news/view.aspx?cdate=15102026&id=91362f75-9c72-4897-a136-eb54030ffdcb",
            "https://www.shorouknews.com.evil.invalid/news/view.aspx?cdate=15102026&id=91362f75-9c72-4897-a136-eb54030ffdcb",
            "https://www.shorouknews.com:8999/news/view.aspx?cdate=15102026&id=91362f75-9c72-4897-a136-eb54030ffdcb",
            "https://www.shorouknews.com/login",
            "https://www.shorouknews.com/news/view.aspx?cdate=2026&id=oops",
        ]:
            with self.subTest(wrong=wrong):
                self.assertFalse(publisher_article(wrong))

    def test_description_can_identify_planning_story_and_de_dupe_url(self):
        item=(TITLE,URL,DESC,"Thu, 15 Oct 2026 13:47:54 +0300")
        matched=extract_candidates(feed([item,item]),NOW)
        self.assertEqual(len(matched),1)
        self.assertEqual(matched[0]["title"],TITLE)
        self.assertTrue(matched[0]["published_cairo"].startswith("2026-10-15T13:47:54"))
        self.assertEqual(matched[0]["url"],URL)

    def test_exact_8am_window_and_future_exclusion(self):
        old=(TITLE,URL,DESC,"Thu, 15 Oct 2026 07:59:00 +0300")
        later=(TITLE,URL,DESC,"Thu, 15 Oct 2026 21:00:00 +0300")
        early=(TITLE,URL,DESC,"Thu, 15 Oct 2026 08:00:00 +0300")
        self.assertEqual(extract_candidates(feed([old,later]),NOW),[])
        self.assertEqual(len(extract_candidates(feed([early]),NOW)),1)

    def test_no_irrelevant_headline_or_unreviewed_publisher(self):
        irrelevant=("مباراة كرة قدم",URL,"تفاصيل نتيجة المباراة","Thu, 15 Oct 2026 13:47:54 +0300")
        other=(TITLE,URL.replace("www.shorouknews.com","hapijournal.com"),
               DESC,"Thu, 15 Oct 2026 13:47:54 +0300")
        self.assertEqual(extract_candidates(feed([irrelevant,other]),NOW),[])

    def test_rejects_xml_entities_and_bad_date(self):
        with self.assertRaisesRegex(ValueError,"xml_entities_forbidden"):
            extract_candidates(b'<!DOCTYPE rss><rss/>',NOW)
        self.assertEqual(extract_candidates(feed([(TITLE,URL,DESC,"bad date")]),NOW),[])
        self.assertEqual(extract_candidates(b"<rss><channel></channel></rss>",NOW),[])


if __name__=="__main__":
    unittest.main()
