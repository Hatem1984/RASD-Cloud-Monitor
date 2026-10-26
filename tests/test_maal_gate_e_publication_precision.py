"""MA'AL evidence contract: a publisher date is never a fabricated hour."""
import unittest
from datetime import date, datetime, timezone

from maal.decision_contracts import (
    BusinessContext, Evidence, ProposedAction, draft_decision_brief,
)


class PublicationPrecisionTests(unittest.TestCase):
    def _sample(self, published):
        return Evidence(
            evidence_id="official-source-item",
            publisher="Verified publisher",
            original_url="https://mped.gov.eg/singlenews?id=7269&lang=ar",
            claim="Published announcement (historical, read-only)",
            published_at=published,
            observed_at=datetime(2026, 10, 26, 12, tzinfo=timezone.utc),
            original_page_sha256="a" * 64,
            status="VERIFIED_ORIGINAL_PAGE",
        )

    def test_date_only_is_retained_without_hour(self):
        evidence = self._sample(date(2026, 10, 17))
        output = draft_decision_brief(
            BusinessContext("synthetic", "infrastructure", "Egypt"),
            (evidence,),
            (ProposedAction("draft_task", "Review verified eligibility",
                            (evidence.evidence_id,)),),
        )
        fact = output["facts_from_verified_inputs"][0]
        self.assertEqual(fact["publication_precision"], "date")
        self.assertEqual(fact["published_at"], "2026-10-17")
        self.assertNotIn("T", fact["published_at"])

    def test_timezone_aware_datetime_retains_exact_precision(self):
        evidence = self._sample(datetime(2026, 10, 17, 9, tzinfo=timezone.utc))
        output = draft_decision_brief(
            BusinessContext("synthetic", "infrastructure", "Egypt"),
            (evidence,),
            (ProposedAction("draft_alert", "Review new item",
                            (evidence.evidence_id,)),),
        )
        self.assertEqual(
            output["facts_from_verified_inputs"][0]["publication_precision"], "datetime")

    def test_naive_datetime_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous_evidence_timestamp"):
            self._sample(datetime(2026, 10, 17, 9)).validate()

    def test_unsupported_publication_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_evidence_publication_date"):
            self._sample("2026-10-17").validate()

    def test_unverified_official_page_still_rejected(self):
        evidence = self._sample(date(2026, 10, 17))
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError, "unverified_evidence"):
            replace(evidence, status="HOLD").validate()


if __name__ == "__main__":
    unittest.main()
