"""Owner-approved Veto conflict exception: monitor but never admit on HOLD."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from monitor import parse_rss, inspect, safe_source_failure_code

NOW=datetime(2026,11,26,16,40,tzinfo=timezone.utc)
CFG=json.loads((Path(__file__).resolve().parents[1]/"sources_newsroom_active.json").read_text(encoding="utf-8"))
FEED=next(x for x in CFG["feeds"] if x["id"]=="vetogate")
OTHER=next(x for x in CFG["feeds"] if x["id"]=="elbalad")
TERM=["Ministry of Planning"]
HOLD="rss_original_publisher_date_conflict_hold"
def rss(feed,title="Ministry of Planning",stamp="Thu, 26 Nov 2026 16:00:00 GMT"):
    return f'<rss><channel><item><title>{title}</title><link>https://{feed["allowed_article_hosts"][0]}/123</link><pubDate>{stamp}</pubDate></item></channel></rss>'.encode()
class DocumentedVetoHold(unittest.TestCase):
    def test_production_scope_keeps_all_sources_and_only_veto_held(self):
        self.assertEqual(len(CFG["feeds"]),14)
        self.assertEqual([f["id"] for f in CFG["feeds"] if f.get("publication_date_conflict_hold") is True],["vetogate"])
    def test_relevant_nonfuture_date_never_admitted(self):
        for strict in (True,False):
            with self.assertRaisesRegex(ValueError,HOLD):
                parse_rss(rss(FEED),FEED,TERM,NOW,require_complete_items=strict)
    def test_unrelated_and_empty_feed_never_false_healthy(self):
        for data in (rss(FEED,"Unrelated"),b"<rss><channel/></rss>"):
            with self.assertRaisesRegex(ValueError,HOLD):
                parse_rss(data,FEED,TERM,NOW,require_complete_items=True)
    def test_future_and_invalid_feed_keep_original_failure_reason(self):
        with self.assertRaisesRegex(ValueError,"rss_original_item_future_date"):
            parse_rss(rss(FEED,stamp="Thu, 26 Nov 2026 18:00:00 GMT"),FEED,TERM,NOW,require_complete_items=True)
        with self.assertRaisesRegex(ValueError,"rss_original_item_date_unverifiable"):
            parse_rss(rss(FEED,stamp="unknown"),FEED,TERM,NOW,require_complete_items=True)
    def test_continued_fetch_other_source_not_blocked_no_send(self):
        cfg={**CFG,"feeds":[FEED,OTHER],"keywords":TERM}
        calls=[]
        def fetch(url,limit):
            calls.append(url)
            return rss(FEED if url==FEED["url"] else OTHER)
        out=inspect(cfg,fetch=fetch,now=NOW,require_complete_items=True)
        self.assertEqual(calls,[FEED["url"],OTHER["url"]])
        self.assertEqual([s["status"] for s in out["sources"]],["failed","ok"])
        self.assertEqual(out["sources"][0]["error_code"],HOLD)
        self.assertEqual([x["source"] for x in out["matched_public_articles"]],[OTHER["name"]])
        self.assertFalse(out["email_sent"])
        self.assertEqual(safe_source_failure_code(ValueError(HOLD)),HOLD)
    def test_explicit_lift_required_not_clock(self):
        with self.assertRaisesRegex(ValueError,HOLD):
            parse_rss(rss(FEED),FEED,TERM,NOW,require_complete_items=True)
        released={**FEED,"publication_date_conflict_hold":False}
        self.assertEqual(len(parse_rss(rss(released),released,TERM,NOW,require_complete_items=True)[1]),1)
