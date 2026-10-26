"""MA'AL Gate D safety acceptance — synthetic inputs, zero external actions."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from maal.decision_contracts import (
    BusinessContext, Evidence, ProposedAction, draft_decision_brief,
)


def example_evidence(**overrides):
    values = {
        "evidence_id": "publisher-proof-1",
        "publisher": "Illustrative publisher (synthetic test)",
        "original_url": "https://example.org/business/item-123",
        "claim": "A competitor publicly announced a new service.",
        "published_at": datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc),
        "observed_at": datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc),
        "original_page_sha256": "a" * 64,
        "status": "VERIFIED_ORIGINAL_PAGE",
    }
    values.update(overrides)
    return Evidence(**values)


def example_action(**overrides):
    values = {
        "kind": "draft_alert",
        "description": "Draft an alert for analyst review.",
        "supporting_evidence_ids": ("publisher-proof-1",),
    }
    values.update(overrides)
    return ProposedAction(**values)


class MaalDecisionProposalContract(unittest.TestCase):
    def setUp(self):
        self.profile = BusinessContext("synthetic-company", "retail", "Dubai")

    def brief(self, evidence=None, actions=None):
        return draft_decision_brief(
            self.profile,
            evidence or (example_evidence(),),
            actions or (example_action(),),
        )

    def test_verified_input_produces_draft_only_with_source_trace(self):
        result = self.brief()
        self.assertEqual(result["status"], "DRAFT_REQUIRES_HUMAN_APPROVAL")
        self.assertTrue(result["human_approval_required"])
        self.assertFalse(result["external_actions_executed"])
        self.assertEqual(result["business_impact"],
                         "NOT_ESTIMATED_WITHOUT_COMPANY_BASELINE")
        self.assertEqual(result["facts_from_verified_inputs"][0]["original_page_sha256"], "a" * 64)
        self.assertEqual(result["proposals_not_executed"][0]["cost_estimate"], None)

    def test_unverified_signal_cannot_be_presented_as_verified_fact(self):
        with self.assertRaisesRegex(ValueError, "unverified_evidence"):
            self.brief(evidence=(example_evidence(status="HOLD_ORIGINAL_IMAGE"),))

    def test_unknown_evidence_id_cannot_support_recommendation(self):
        with self.assertRaisesRegex(ValueError, "lacks_verified_evidence"):
            self.brief(actions=(example_action(supporting_evidence_ids=("invented",)),))

    def test_sensitive_action_cannot_execute_or_be_proposed(self):
        with self.assertRaisesRegex(ValueError, "unsafe_or_empty_proposed_action"):
            self.brief(actions=(example_action(kind="send_customer_email"),))

    def test_cost_without_explicit_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ungrounded_financial_estimate"):
            self.brief(actions=(example_action(cost_estimate=Decimal("950"),
                                                 cost_currency="EGP"),))

    def test_grounded_cost_still_requires_human_approval(self):
        result = self.brief(actions=(example_action(
            cost_estimate=Decimal("950"), cost_currency="EGP",
            cost_basis_evidence_id="publisher-proof-1"),))
        self.assertEqual(result["proposals_not_executed"][0]["cost_estimate"], "950")
        self.assertTrue(result["human_approval_required"])
        self.assertFalse(result["external_actions_executed"])

    def test_ambiguous_published_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous_evidence_timestamp"):
            self.brief(evidence=(example_evidence(
                published_at=datetime(2026, 10, 26, 9, 0)),))

    def test_non_https_original_page_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "original_evidence_https_required"):
            self.brief(evidence=(example_evidence(original_url="http://example.org"),))


if __name__ == "__main__":
    unittest.main()
