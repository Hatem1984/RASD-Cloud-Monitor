"""Gate B — no-network regression for delayed GitHub CAS read visibility.

Never retries a PUT, reserves twice, sends email, or logs private ledger data.
"""
import unittest
from unittest.mock import patch

from delivery_bridge import PrivateGitHubLedger


KEY = "a" * 24
PREVIOUS_SHA = "old-contents-sha"
CURRENT_SHA = "new-contents-sha"


def state_with_reservation():
    return {
        "schema_version": 2,
        "approved_recipient_sha256": "1" * 64,
        "entries": {
            KEY: {"status": "reserved", "reserved_at": "2026-10-26T12:00:00+00:00"}
        },
    }


def empty_state():
    state = state_with_reservation()
    state["entries"] = {}
    return state


class PrivateLedgerVisibilityReadback(unittest.TestCase):
    def setUp(self):
        self.ledger = PrivateGitHubLedger("offline_test_token_long_enough")
        self.expected = state_with_reservation()
        self.old = empty_state()

    @patch("delivery_bridge.time.sleep")
    def test_delayed_visibility_confirms_only_after_matching_exact_state(self, sleep):
        with patch.object(self.ledger, "_request",
                          return_value={"commit": {"sha": "github-new-commit"}}) as request:
            with patch.object(self.ledger, "read", side_effect=[
                    (self.old, PREVIOUS_SHA),
                    (self.old, PREVIOUS_SHA),
                    (self.expected, CURRENT_SHA),
            ]) as read:
                self.ledger.write(self.expected, PREVIOUS_SHA)
        self.assertEqual(request.call_count, 1)  # no CAS PUT retry
        self.assertEqual(read.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("delivery_bridge.time.sleep")
    def test_fake_put_receipt_stays_hold_after_bounded_read_rechecks(self, sleep):
        with patch.object(self.ledger, "_request",
                          return_value={"commit": {"sha": "fake-ack"}}) as request:
            with patch.object(self.ledger, "read",
                              return_value=(self.old, PREVIOUS_SHA)) as read:
                with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
                    self.ledger.write(self.expected, PREVIOUS_SHA)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(read.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("delivery_bridge.time.sleep")
    def test_unrelated_concurrent_ledger_content_still_holds(self, sleep):
        concurrent = state_with_reservation()
        concurrent["entries"]["b" * 24] = {
            "status": "reserved", "reserved_at": "2026-10-26T12:01:00+00:00"
        }
        with patch.object(self.ledger, "_request",
                          return_value={"commit": {"sha": "github-new-commit"}}):
            with patch.object(self.ledger, "read",
                              return_value=(concurrent, CURRENT_SHA)):
                with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
                    self.ledger.write(self.expected, PREVIOUS_SHA)
        self.assertEqual(sleep.call_count, 2)

    @patch("delivery_bridge.time.sleep")
    def test_invalid_commit_receipt_does_not_read_or_retry(self, sleep):
        with patch.object(self.ledger, "_request", return_value={"commit": {}}) as req:
            with patch.object(self.ledger, "read") as read:
                with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_receipt_invalid"):
                    self.ledger.write(self.expected, PREVIOUS_SHA)
        self.assertEqual(req.call_count, 1)
        read.assert_not_called()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
