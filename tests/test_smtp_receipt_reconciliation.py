"""Offline regressions for ambiguous GitHub receipt readback AFTER SMTP.

Never sends mail, never reads private GitHub or credentials, never invents acceptance.
"""
import copy
import unittest
from unittest.mock import patch

from delivery_bridge import PrivateGitHubLedger
from scheduled_rasd import safe_scheduled_hold_reason

KEY = "a" * 24
STAMP = "2026-10-24T14:38:52+00:00"
RECEIPT = "<rasd-" + "b" * 24 + "@gmail.com>"


def state(status="reserved", message_id=None):
    item = {"kind": "interval_item", "status": status,
            "reserved_at": "2026-10-24T14:38:46+00:00"}
    if status == "smtp_accepted":
        item.update({"accepted_at": STAMP, "message_id": message_id or RECEIPT})
    return {"schema_version": 2, "approved_recipient_sha256": "0" * 64,
            "entries": {KEY: item}}


class DurableReceiptReconciliation(unittest.TestCase):
    def setUp(self):
        self.ledger = PrivateGitHubLedger("offline-placeholder-token-123")
        self.initial = state()
        self.final = state("smtp_accepted")

    def run_probe(self, later_state):
        with (
            patch.object(self.ledger, "read",
                         side_effect=[(copy.deepcopy(self.initial), "before-sha"),
                                      (copy.deepcopy(later_state), "after-sha")]) as reads,
            patch.object(self.ledger, "write",
                         side_effect=RuntimeError("private_ledger_commit_not_visible")) as writes,
            patch("delivery_bridge.now_iso", return_value=STAMP),
        ):
            self.ledger.mark_smtp_accepted_many([KEY], RECEIPT)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(writes.call_count, 1)

    def test_readonly_reconcile_exact_persisted_receipt_after_ambiguous_write(self):
        # Matches a real failure pattern: SMTP already accepted + private
        # ledger has exact article, accepted timestamp and message ID.
        self.run_probe(self.final)

    def test_no_false_accept_if_persisted_receipt_is_different(self):
        bad = state("smtp_accepted", "<rasd-" + "c" * 24 + "@gmail.com>")
        with self.assertRaisesRegex(RuntimeError,
                                    "smtp_receipt_persistence_uncertain_manual_reconcile"):
            self.run_probe(bad)

    def test_no_false_accept_when_no_persistent_smtp_receipt_exists(self):
        with self.assertRaisesRegex(RuntimeError,
                                    "smtp_receipt_persistence_uncertain_manual_reconcile"):
            self.run_probe(state())

    def test_readback_failure_after_write_keeps_manual_hold(self):
        with (
            patch.object(self.ledger, "read",
                         side_effect=[(self.initial, "sha"), RuntimeError("offline")]),
            patch.object(self.ledger, "write",
                         side_effect=RuntimeError("offline write")),
            patch("delivery_bridge.now_iso", return_value=STAMP),
        ):
            with self.assertRaisesRegex(RuntimeError,
                                        "smtp_receipt_persistence_uncertain_manual_reconcile"):
                self.ledger.mark_smtp_accepted_many([KEY], RECEIPT)

    def test_single_exact_durable_receipt_reconciles_without_second_write(self):
        with (
            patch.object(self.ledger, "read", side_effect=[
                (self.initial, "old"), (self.final, "new")]) as reads,
            patch.object(self.ledger, "write",
                         side_effect=RuntimeError("private_ledger_request_failed")) as writes,
            patch("delivery_bridge.now_iso", return_value=STAMP),
        ):
            self.ledger.mark_smtp_accepted(KEY, RECEIPT)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(writes.call_count, 1)

    def test_single_missing_or_conflicting_receipt_remains_hold(self):
        for later, sha in [
            (self.initial, "new"),
            (state("smtp_accepted", "<rasd-" + "c" * 24 + "@gmail.com>"), "new"),
            (self.final, "old"),
            (self.final, ""),
        ]:
            with (
                self.subTest(sha=sha, later=later),
                patch.object(self.ledger, "read", side_effect=[
                    (self.initial, "old"), (later, sha)]) as reads,
                patch.object(self.ledger, "write",
                             side_effect=RuntimeError("private_ledger_commit_not_visible")) as writes,
                patch("delivery_bridge.now_iso", return_value=STAMP),
            ):
                with self.assertRaisesRegex(RuntimeError,
                                            "smtp_receipt_persistence_uncertain_manual_reconcile"):
                    self.ledger.mark_smtp_accepted(KEY, RECEIPT)
                self.assertEqual(reads.call_count, 2)
                self.assertEqual(writes.call_count, 1)

    def test_single_unavailable_reconciliation_read_stays_hold(self):
        with (
            patch.object(self.ledger, "read", side_effect=[
                (self.initial, "old"), RuntimeError("offline")]) as reads,
            patch.object(self.ledger, "write",
                         side_effect=RuntimeError("private_ledger_request_failed")) as writes,
            patch("delivery_bridge.now_iso", return_value=STAMP),
        ):
            with self.assertRaisesRegex(RuntimeError,
                                        "smtp_receipt_persistence_uncertain_manual_reconcile"):
                self.ledger.mark_smtp_accepted(KEY, RECEIPT)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(writes.call_count, 1)

    def test_sanitized_public_failure_code_never_reflects_sensitive_exceptions(self):
        self.assertEqual(
            safe_scheduled_hold_reason(RuntimeError("private_ledger_commit_not_visible")),
            "private_ledger_commit_not_visible")
        self.assertEqual(
            safe_scheduled_hold_reason(RuntimeError(
                "https://untrusted.publisher.invalid/?secret=private-token")),
            "other_held_failure")
        self.assertEqual(
            safe_scheduled_hold_reason(ValueError("recipient@example.com")),
            "other_held_failure")
        self.assertEqual(
            safe_scheduled_hold_reason(RuntimeError(
                "smtp_receipt_persistence_uncertain_manual_reconcile")),
            "smtp_receipt_persistence_uncertain_manual_reconcile")


if __name__ == "__main__":
    unittest.main()
