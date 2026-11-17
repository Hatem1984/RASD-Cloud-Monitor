import unittest
from datetime import datetime, timezone
from rasd_candidate_native_rss_qa import try_source, CANDIDATES

class SourceAdmissionQA(unittest.TestCase):
    def test_invalid_original_xml_is_held(self):
        a=try_source(CANDIDATES[0],[],datetime.now(timezone.utc),
                     fetch=lambda *_: b'<html>not an RSS feed</html>')
        self.assertEqual(a["status"],"HOLD")
        self.assertEqual(a["original_rss_links"],0)
        self.assertFalse(a["original_jpeg_verified"])

    def test_redirect_is_never_forgiven(self):
        def denied(*_):
            raise RuntimeError("feed_redirect_blocked")
        a=try_source(CANDIDATES[1],[],datetime.now(timezone.utc),
                     fetch=denied)
        self.assertEqual(a["reason"],"feed_redirect_blocked")
        self.assertEqual(a["status"],"HOLD")

    def test_untrusted_network_exception_text_cannot_appear(self):
        def denied(*_):
            raise ValueError("private_key=NEVER_PRINT")
        a=try_source(CANDIDATES[2],[],datetime.now(timezone.utc),fetch=denied)
        self.assertNotIn("NEVER_PRINT",str(a))
        self.assertFalse(a["original_jpeg_verified"])

if __name__=="__main__":
    unittest.main()
