"""Offline CAS readback tests: a successful PUT is never retried."""
import copy
import unittest
from unittest.mock import patch
from delivery_bridge import PrivateGitHubLedger, reserve_entry, LEDGER_READBACK_DELAYS

KEY = "a" * 24
STAMP = "2026-11-25T14:35:00+00:00"
INITIAL = {"schema_version": 2, "approved_recipient_sha256": "0" * 64, "entries": {}}


class CASReadbackTests(unittest.TestCase):
    def setUp(self):
        self.ledger = PrivateGitHubLedger("offline-placeholder-token-123")
        self.new, _ = reserve_entry(copy.deepcopy(INITIAL), KEY, STAMP)
        self.old = (copy.deepcopy(INITIAL), "old-sha")
        self.expected = (self.new, "new-sha")

    def check(self, reads, error=None, delay_count=0):
        with (
            patch.object(self.ledger, "_request", return_value={"commit": {"sha": "commit-sha"}}) as request,
            patch.object(self.ledger, "read", side_effect=reads) as read,
            patch("delivery_bridge.time.sleep") as sleep,
        ):
            if error:
                with self.assertRaisesRegex(RuntimeError, error):
                    self.ledger.write(self.new, "old-sha")
            else:
                self.ledger.write(self.new, "old-sha")
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[0], "PUT")
            self.assertEqual(request.call_args.args[1]["sha"], "old-sha")
            self.assertEqual(read.call_count, delay_count + 1)
            self.assertEqual([x.args[0] for x in sleep.call_args_list], list(LEDGER_READBACK_DELAYS[:delay_count]))

    def test_immediate_exact_readback(self):
        self.check([self.expected])

    def test_stale_then_exact_readback(self):
        self.check([self.old, self.expected], delay_count=1)

    def test_last_allowed_readback(self):
        self.check([self.old]*3+[self.expected], delay_count=3)

    def test_false_ack_remains_hold(self):
        self.check([self.old]*4, "private_ledger_commit_not_visible", 3)

    def test_unexpected_new_blob_stops_immediately(self):
        conflicting = copy.deepcopy(self.new)
        conflicting["entries"]["b"*24] = {"status":"reserved","reserved_at":STAMP}
        self.check([(conflicting,"other-sha")], "private_ledger_commit_not_visible")

    def test_same_blob_sha_cannot_prove_new_commit(self):
        self.check([(self.new,"old-sha")]*4, "private_ledger_commit_not_visible", 3)

    def test_unavailable_read_never_retries_write(self):
        self.check([RuntimeError("private_ledger_request_failed")], "private_ledger_request_failed")

    def test_invalid_commit_receipt_stops_before_read(self):
        with patch.object(self.ledger,"_request",return_value={"commit":{}}) as request, patch.object(self.ledger,"read") as read:
            with self.assertRaisesRegex(RuntimeError,"private_ledger_commit_receipt_invalid"):
                self.ledger.write(self.new,"old-sha")
            request.assert_called_once()
            read.assert_not_called()

if __name__ == "__main__":
    unittest.main()
