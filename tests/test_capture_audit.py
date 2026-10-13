"""Only fixed, sanitized failure codes reach the public Actions diagnostics."""
import unittest

from gate11_runner import record_capture_rejection


class CaptureRejectionAuditTests(unittest.TestCase):
    def test_expected_reason_is_counted_without_article_or_website_metadata(self):
        results = {"rejected_capture": 0, "capture_rejection_reasons": {}}
        record_capture_rejection(results, "page_content_unavailable")
        record_capture_rejection(results, "title_mismatch")
        record_capture_rejection(results, "title_mismatch")
        self.assertEqual(results["rejected_capture"], 3)
        self.assertEqual(results["capture_rejection_reasons"], {
            "page_content_unavailable": 1, "title_mismatch": 2,
        })

    def test_untrusted_exception_text_is_not_reflected_in_public_logs(self):
        results = {"rejected_capture": 0, "capture_rejection_reasons": {}}
        record_capture_rejection(results, "unsafe text with private URL or token")
        record_capture_rejection(results, None)
        self.assertEqual(results["capture_rejection_reasons"], {"other": 2})
        self.assertEqual(results["rejected_capture"], 2)


if __name__ == "__main__":
    unittest.main()
