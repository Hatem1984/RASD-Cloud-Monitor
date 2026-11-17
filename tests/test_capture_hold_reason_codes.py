"""Offline regression: genuine first-party capture HOLD reasons stay diagnostic.

No browser, private ledger, external HTTP, email or recipient operations.
"""
import unittest

from cloud_proof_report import classify_failure
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES, record_capture_rejection


class CaptureHoldReasonCodes(unittest.TestCase):
    def test_known_original_page_failures_do_not_collapse_to_other(self):
        known = (
            "missing_original_headline",
            "original_headline_not_in_article",
            "original_headline_out_of_frame",
            "visual_qa_suspicious_flat_original_lead_media",
            "source_identity_mismatch",
            "screenshot_digest_mismatch",
        )
        for reason in known:
            with self.subTest(reason=reason):
                self.assertIn(reason, SAFE_CAPTURE_FAILURE_CODES)
                self.assertEqual(classify_failure(reason), reason)
                metrics = {"rejected_capture": 0, "capture_rejection_reasons": {}}
                source = {"rejected": 0, "rejection_reasons": {}}
                record_capture_rejection(metrics, reason, source)
                self.assertEqual(metrics["capture_rejection_reasons"], {reason: 1})
                self.assertEqual(source["rejection_reasons"], {reason: 1})

    def test_untrusted_failure_data_never_reaches_public_diagnosis(self):
        unknown = (
            "publisher secret https://example.invalid/article?token=private",
            "unexpected playwright exception details",
            "",
            None,
        )
        for reason in unknown:
            with self.subTest(reason=reason):
                self.assertEqual(classify_failure(reason), "other")
                metrics = {"rejected_capture": 0, "capture_rejection_reasons": {}}
                record_capture_rejection(metrics, reason)
                self.assertEqual(metrics["capture_rejection_reasons"], {"other": 1})

    def test_all_known_browser_return_reasons_are_allowlisted(self):
        # Known reason codes returned by capture_public.capture_publisher().
        reasons = (
            "publisher_not_approved",
            "publisher_no_http_response",
            "publisher_http_failure",
            "publisher_access_refused",
            "publisher_article_unavailable",
            "publisher_rate_limited",
            "publisher_server_error",
            "redirect_outside_publisher",
            "page_content_unavailable",
            "not_a_planning_article",
            "missing_original_headline",
            "original_headline_not_in_article",
            "original_headline_out_of_frame",
            "original_article_image_not_loaded",
            "screenshot_too_small",
            "visual_qa_too_small_dimensions",
            "visual_qa_blank_or_low_content",
            "visual_qa_invalid_image",
            "visual_qa_suspicious_flat_original_lead_media",
            "invalid_jpeg_signature",
            "TimeoutError",
            "Error",
        )
        for reason in reasons:
            with self.subTest(reason=reason):
                self.assertEqual(classify_failure(reason), reason)


if __name__ == "__main__":
    unittest.main()
