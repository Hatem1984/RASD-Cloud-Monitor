"""Stage 02 future publisher date guard; synthetic XML, no network or mail."""
import unittest
from datetime import datetime, timezone
from monitor import parse_rss, inspect, safe_source_failure_code

NOW = datetime(2026, 11, 26, 13, 25, tzinfo=timezone.utc)
FEED = {"id":"vetogate","name":"Veto test","url":"https://www.vetogate.com/rss.aspx","allowed_article_hosts":["www.vetogate.com"]}
SECOND = {"id":"elbalad","name":"Other test","url":"https://www.elbalad.news/rss.aspx","allowed_article_hosts":["www.elbalad.news"]}
KEYWORDS = ["Ministry of Planning"]
FUTURE = "Thu, 26 Nov 2026 15:25:09 GMT"
CURRENT = "Thu, 26 Nov 2026 13:00:00 GMT"

def xml(feed, rows):
    return ("<rss><channel>"+"".join(
        f"<item><title>{title}</title><link>https://{feed['allowed_article_hosts'][0]}/{i}</link><pubDate>{stamp}</pubDate></item>"
        for i,(title,stamp) in enumerate(rows,1))+"</channel></rss>").encode()

class FutureSourceHealth(unittest.TestCase):
    def test_all_future_nonmatching_items_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"rss_original_item_future_date"):
            parse_rss(xml(FEED,[("Other news",FUTURE),("More news",FUTURE)]),FEED,KEYWORDS,NOW,require_complete_items=True)
    def test_relevant_future_item_not_silently_discarded(self):
        with self.assertRaisesRegex(ValueError,"rss_original_item_future_date"):
            parse_rss(xml(FEED,[("Other news",CURRENT),("Ministry of Planning",FUTURE)]),FEED,KEYWORDS,NOW,require_complete_items=True)
    def test_other_future_item_does_not_suppress_current_match(self):
        count, matches=parse_rss(xml(FEED,[("Ministry of Planning",CURRENT),("Other news",FUTURE)]),FEED,KEYWORDS,NOW,require_complete_items=True)
        self.assertEqual((count,len(matches)),(2,1))
        self.assertEqual(matches[0]["published"],CURRENT)
    def test_boundary_preserves_existing_30_minute_tolerance(self):
        stamp="Thu, 26 Nov 2026 13:55:00 GMT"
        count,matches=parse_rss(xml(FEED,[("Ministry of Planning",stamp)]),FEED,KEYWORDS,NOW,require_complete_items=True)
        self.assertEqual((count,len(matches)),(1,1))
    def test_legacy_preview_still_filters_future(self):
        count,matches=parse_rss(xml(FEED,[("Ministry of Planning",FUTURE)]),FEED,KEYWORDS,NOW)
        self.assertEqual((count,matches),(1,[]))
    def test_partial_source_status_no_send_and_no_retry(self):
        cfg={"feeds":[FEED,SECOND],"keywords":KEYWORDS,"max_feed_bytes":1500000,"recent_hours":72}
        calls=[]
        def fetch(url,limit):
            calls.append(url)
            f=FEED if url==FEED["url"] else SECOND
            return xml(f,[("Other news",FUTURE if f is FEED else CURRENT)])
        result=inspect(cfg,fetch=fetch,now=NOW,require_complete_items=True)
        self.assertEqual(calls,[FEED["url"],SECOND["url"]])
        self.assertEqual([x["status"] for x in result["sources"]],["failed","ok"])
        self.assertEqual(result["sources"][0]["error_code"],"rss_original_item_future_date")
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertEqual(safe_source_failure_code(ValueError("rss_original_item_future_date")),"rss_original_item_future_date")
