"""Offline publisher timestamp diagnostic contracts: never invent dates."""
import json
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import monitor
import rasd_stage2_observer_qa as observer

CONFIG=json.loads((Path(__file__).resolve().parents[1]/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
MS=next(f for f in CONFIG["feeds"] if f["id"]=="masrawy")
HAPI=next(f for f in CONFIG["feeds"] if f["id"]=="hapi")
MS_XML=("""<rss><channel><item>
<title>وزارة التخطيط تعلن مشروعات جديدة</title>
<link>https://www.masrawy.com/news/news_egypt/details/2026/11/5/test</link>
<pubDate>11/05/2026 12:00:00 PM</pubDate>
</item></channel></rss>""").encode("utf-8")
OK_XML=("""<rss><channel><item>
<title>خبر تجريبي ليس عن الوزارة</title>
<link>https://hapijournal.com/news/qa/other</link>
<pubDate>Thu, 05 Nov 2026 12:00:00 +0200</pubDate>
</item></channel></rss>""").encode("utf-8")


def source_result(reason):
    def fetch(url,limit):
        return MS_XML if url==MS["url"] else OK_XML
    with patch("masrawy_original_date.original_pubdate",
               side_effect=RuntimeError(reason)):
        return monitor.inspect({**CONFIG,"feeds":[MS,HAPI]},
            fetch=fetch,now=datetime(2026,11,5,10,15,tzinfo=timezone.utc),
            article_limit=200,require_complete_items=True)


class StrictMasrawyDateReason(unittest.TestCase):
    def test_transport_failure_is_reported_without_guessing_clock(self):
        r=source_result("masrawy_original_page_request_hold")
        f=r["sources"][0]
        self.assertEqual(f["status"],"failed")
        self.assertEqual(f["verified_links"],0)
        self.assertEqual(f["failure_code"],"rss_original_item_date_unverifiable")
        self.assertEqual(f["publisher_date_reason"],"masrawy_original_page_request_hold")
        self.assertFalse(r["email_sent"])

    def test_broken_original_jsonld_is_not_mislabelled_transport(self):
        r=source_result("masrawy_publisher_publication_date_unverified")
        f=r["sources"][0]
        self.assertEqual(f["publisher_date_reason"],
                         "masrawy_publisher_publication_date_unverified")
        self.assertEqual(f["status"],"failed")

    def test_arbitrary_exception_text_never_enters_receipt(self):
        r=source_result("SECRET_PUBLISHER_TOKEN: BAD")
        f=r["sources"][0]
        self.assertEqual(f["publisher_date_reason"],
                         "masrawy_original_date_unknown_hold")
        self.assertNotIn("SECRET_PUBLISHER_TOKEN",json.dumps(r))

    def test_observer_keeps_only_approved_publisher_reason(self):
        rows=[{"feed_id":x["id"],"status":"ok","verified_links":10}
              for x in CONFIG["feeds"]]
        idx=next(i for i,x in enumerate(CONFIG["feeds"]) if x["id"]=="masrawy")
        rows[idx]={"feed_id":"masrawy","status":"failed","verified_links":0,
                   "failure_code":"rss_original_item_date_unverifiable",
                   "publisher_date_reason":"masrawy_original_page_request_hold",
                   "leaked_header":"private-secret"}
        o=observer.observe(mode="probe",now=datetime(2026,11,5,10,15,tzinfo=timezone.utc),
            config=CONFIG,manifest={"active_version":28,"sha256":"b"*64,
                                    "settings":{"topics":[]}},
            monitor=monitor,env={},inspector=lambda *a,**k:{
                "sources":rows,"matched_public_articles":[]})
        self.assertEqual(o["status"],"HOLD_SOURCE_FAILURE")
        self.assertEqual(o["sources"][idx]["publisher_date_reason"],
                         "masrawy_original_page_request_hold")
        self.assertNotIn("private-secret",json.dumps(o))
        self.assertFalse(o["smtp_sent"])

if __name__=="__main__":unittest.main()
