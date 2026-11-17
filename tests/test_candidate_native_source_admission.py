"""Six prospective news sources cannot enter production without full proof."""
import unittest

from rasd_candidate_native_source_admission_no_send import (
    CANDIDATES, probe, validate_native_feed,
)

VALID = (b"<rss><channel><item><title>Ministry</title>"
         b"<link>https://www.youm7.com/story/1</link>"
         b"<pubDate>Tue, 17 Nov 2026 18:00:00 +0200</pubDate>"
         b"</item></channel></rss>")


class OriginalCandidateOnlyAcceptance(unittest.TestCase):
    def test_valid_feed_is_rss_only_not_screenshot_approved(self):
        out = probe(CANDIDATES[0],fetch=lambda _: VALID)
        self.assertEqual(out["status"],"RSS_STAGE_QUALIFIED_ONLY")
        self.assertFalse(out["original_screenshot_verified"])
        self.assertFalse(out["activated"])
        self.assertEqual(out["original_links"],1)

    def test_html_is_never_called_rss(self):
        self.assertEqual(validate_native_feed(
            b"<html><body>Publisher site</body></html>",
            ("www.youm7.com",))["reason"],"NOT_NATIVE_RSS")

    def test_unzoned_rss_item_date_held(self):
        bad=VALID.replace(b"18:00:00 +0200",b"18:00:00")
        self.assertEqual(validate_native_feed(
            bad,("www.youm7.com",))["reason"],
            "PUBLISHER_DATE_UNVERIFIABLE")

    def test_external_article_link_blocks_even_same_article_title(self):
        bad=VALID.replace(b"www.youm7.com",b"attacker.invalid")
        self.assertEqual(validate_native_feed(
            bad,("www.youm7.com",))["reason"],
            "ARTICLE_ORIGIN_UNVERIFIED")

    def test_dtd_and_malformed_xml_fail_closed(self):
        self.assertEqual(validate_native_feed(
            b'<!DOCTYPE rss><rss/>',("www.youm7.com",))["reason"],
            "RSS_XML_ENTITY_FORBIDDEN")
        self.assertEqual(validate_native_feed(
            b'<rss><channel><item>',("www.youm7.com",))["reason"],
            "RSS_XML_MALFORMED")

    def test_untrusted_exception_does_not_leak(self):
        def broken(_):
            raise RuntimeError("secret=SHOULD_NOT_PRINT")
        result=probe(CANDIDATES[0],fetch=broken)
        self.assertEqual(result["reason"],"OTHER_HOLD")
        self.assertNotIn("SHOULD_NOT_PRINT",str(result))

    def test_six_ids_unique_and_publisher_owned_https(self):
        self.assertEqual(len(CANDIDATES),6)
        self.assertEqual(len({x[0] for x in CANDIDATES}),6)
        for _,url,_ in CANDIDATES:
            self.assertTrue(url.startswith("https://"))


if __name__=="__main__":
    unittest.main()
