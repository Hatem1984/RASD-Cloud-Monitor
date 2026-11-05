"""Original publisher RSS encoding repair: only exact bare '&', no invented news.

Uses synthetic XML fixtures, no internet, no mail. Original publisher XML is
never overwritten and all recovered article identity/time guards still apply.
"""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import monitor

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
NEWS=next(f for f in CONFIG["feeds"] if f["id"]=="almasryalyoum")
HAPI=next(f for f in CONFIG["feeds"] if f["id"]=="hapi")
CLOCK=datetime(2026,11,5,10,15,tzinfo=timezone.utc)
LINK="https://www.almasryalyoum.com/news/details/9999999"
def fixture(*,headline="وزارة التخطيط R&D",published="Thu, 05 Nov 2026 12:00:00 +0200",url=LINK):
    return (f"<rss><channel><item><title>{headline}</title><link>{url}</link>"
            f"<pubDate>{published}</pubDate>"
            "<description><![CDATA[وزارة التخطيط & مهم]]></description>"
            "</item></channel></rss>").encode("utf-8")
def check(raw,feed=NEWS,strict=True):
    return monitor.inspect({**CONFIG,"feeds":[feed]},
        fetch=lambda _url,_size:raw,now=CLOCK,article_limit=200,
        require_complete_items=strict)

class StrictNativeAmpRecovery(unittest.TestCase):
    def test_one_bad_amp_preserves_literal_title_and_complete_original_time(self):
        raw=fixture()
        original=bytes(raw)
        result=check(raw)
        source=result["sources"][0]
        self.assertEqual(source["status"],"ok")
        self.assertEqual(source["verified_links"],1)
        self.assertEqual(source["rss_xml_ampersand_recovery_count"],1)
        self.assertNotIn("xml_error_code",source)
        self.assertEqual(result["planning_headline_matches"],1)
        article=result["matched_public_articles"][0]
        self.assertEqual(article["headline"],"وزارة التخطيط R&D")
        self.assertEqual(article["url"],LINK)
        self.assertEqual(article["published"],"Thu, 05 Nov 2026 12:00:00 +0200")
        self.assertEqual(raw,original)
        self.assertFalse(result["email_sent"])
    def test_malformed_other_publisher_never_recovers(self):
        with patch.object(monitor,"sleep",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"all_public_RSS_sources_failed"):
                check(fixture().replace(LINK.encode(),b"https://hapijournal.com/qa"),
                      feed=HAPI)
    def test_only_strict_stage2_can_repair_publisher_malformed_xml(self):
        with patch.object(monitor,"sleep",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"all_public_RSS_sources_failed"):
                check(fixture(),strict=False)
    def test_wrong_article_host_still_rejected_after_syntax_recovery(self):
        with self.assertRaisesRegex(RuntimeError,"all_public_RSS_sources_failed"):
            check(fixture(url="https://evil.example.invalid/plan"))
    def test_missing_original_pubdate_still_hold(self):
        with self.assertRaisesRegex(RuntimeError,"all_public_RSS_sources_failed"):
            check(fixture(published=""))
    def test_cdata_is_never_escaped_or_modified(self):
        data=b"<rss><channel><item><description><![CDATA[A & B]]></description></item></channel></rss>"
        self.assertIsNone(monitor._recover_native_rss_amp_escapes(data))
        raw=b"<rss><channel><item><title>A & B</title><description><![CDATA[R&D &amp; C]]></description></item></channel></rss>"
        recovered=monitor._recover_native_rss_amp_escapes(raw)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered[1],1)
        self.assertIn(b"<![CDATA[R&D &amp; C]]>",recovered[0])
        self.assertIn(b"<title>A &amp; B</title>",recovered[0])
    def test_xml_comments_are_not_modified(self):
        raw=b"<rss><!-- original R&D --><channel><item><title>A & B</title></item></channel></rss>"
        recovered=monitor._recover_native_rss_amp_escapes(raw)
        self.assertEqual(recovered[1],1)
        self.assertIn(b"<!-- original R&D -->",recovered[0])
    def test_too_many_broken_entities_not_guessed(self):
        raw=b"<rss><channel><item><title>A & B & C & D & E & F</title></item></channel></rss>"
        self.assertIsNone(monitor._recover_native_rss_amp_escapes(raw))
    def test_dtd_entity_not_normalized(self):
        raw=b'<!DOCTYPE rss [<!ENTITY x "test">]><rss><channel><item><title>A & B</title></item></channel></rss>'
        self.assertIsNone(monitor._recover_native_rss_amp_escapes(raw))
    def test_unbalanced_cdata_or_comment_refuses_recovery(self):
        self.assertIsNone(monitor._recover_native_rss_amp_escapes(b"<rss><![CDATA[ A & B"))
        self.assertIsNone(monitor._recover_native_rss_amp_escapes(b"<rss><!-- A & B"))
    def test_already_well_formed_rss_is_not_changed(self):
        raw=fixture(headline="وزارة التخطيط R&amp;D")
        result=check(raw)
        self.assertEqual(result["sources"][0]["status"],"ok")
        self.assertNotIn("rss_xml_ampersand_recovery_count",result["sources"][0])

if __name__=="__main__": unittest.main()
