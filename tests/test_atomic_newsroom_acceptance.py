"""Offline private-CAS batch delivery acceptance safety tests.

No Gmail, no internet, no private repo; verifies the single durable write
needed when one Word message contains more than one verified newsroom item.
"""
from __future__ import annotations
import copy
import unittest
from unittest.mock import MagicMock

from delivery_bridge import PrivateGitHubLedger


def fake_state(statuses):
    entries={}
    for key,status in statuses.items():
        entries[key]={
            "status":status,
            "reserved_at":"2026-10-22T22:00:00+00:00",
            "kind":"interval_item",
        }
        if status=="smtp_accepted":
            entries[key].update({
                "accepted_at":"2026-10-22T22:10:00+00:00",
                "message_id":"<rasd-prior@gmail.com>",
            })
    return {
        "schema_version":2,
        "approved_recipient_sha256":"a"*64,
        "entries":entries,
    }


class AtomicNewsroomAcceptance(unittest.TestCase):
    def make_ledger(self,state):
        ledger=PrivateGitHubLedger("fixture-only-key-long-enough")
        ledger.read=MagicMock(return_value=(copy.deepcopy(state),"sha-old"))
        ledger.write=MagicMock()
        return ledger

    def test_two_article_mail_has_single_private_cas_commit(self):
        a,b="a"*24,"b"*24
        ledger=self.make_ledger(fake_state({a:"reserved",b:"reserved"}))
        ledger.mark_smtp_accepted_many([a,b],"<rasd-batch-receipt@gmail.com>")
        ledger.write.assert_called_once()
        after,sha=ledger.write.call_args.args
        self.assertEqual(sha,"sha-old")
        self.assertEqual(set(after["entries"]),{a,b})
        self.assertEqual({after["entries"][k]["status"] for k in (a,b)},
                         {"smtp_accepted"})
        self.assertEqual({after["entries"][k]["message_id"] for k in (a,b)},
                         {"<rasd-batch-receipt@gmail.com>"})
        self.assertEqual(len({after["entries"][k]["accepted_at"] for k in (a,b)}),1)

    def test_one_bad_reservation_aborts_before_any_write(self):
        a,b="a"*24,"b"*24
        ledger=self.make_ledger(fake_state({a:"reserved",b:"smtp_accepted"}))
        with self.assertRaisesRegex(RuntimeError,"batch_reservation_not_eligible"):
            ledger.mark_smtp_accepted_many([a,b],"<rasd-batch@gmail.com>")
        ledger.write.assert_not_called()

    def test_unknown_article_aborts_before_any_write(self):
        a,b="a"*24,"b"*24
        ledger=self.make_ledger(fake_state({a:"reserved"}))
        with self.assertRaisesRegex(RuntimeError,"batch_reservation_not_eligible"):
            ledger.mark_smtp_accepted_many([a,b],"<rasd-batch@gmail.com>")
        ledger.write.assert_not_called()

    def test_duplicate_and_excessive_batch_fails_before_private_read(self):
        a="a"*24
        ledger=self.make_ledger(fake_state({a:"reserved"}))
        for rows in [[],[a,a],[a]*16,("a",)]:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    ledger.mark_smtp_accepted_many(rows,"<rasd-batch@gmail.com>")
        ledger.read.assert_not_called()
        ledger.write.assert_not_called()

    def test_invalid_receipt_never_writes_even_if_all_reserved(self):
        a,b="a"*24,"b"*24
        ledger=self.make_ledger(fake_state({a:"reserved",b:"reserved"}))
        with self.assertRaises(ValueError):
            ledger.mark_smtp_accepted_many([a,b],"forged-email")
        ledger.write.assert_not_called()

    def test_lost_private_write_raises_without_replaying_smtp(self):
        a,b="a"*24,"b"*24
        ledger=self.make_ledger(fake_state({a:"reserved",b:"reserved"}))
        ledger.write.side_effect=RuntimeError("private_ledger_request_failed")
        with self.assertRaisesRegex(RuntimeError,"smtp_receipt_persistence_uncertain_manual_reconcile"):
            ledger.mark_smtp_accepted_many([a,b],"<rasd-batch@gmail.com>")
        ledger.write.assert_called_once()


if __name__=="__main__":
    unittest.main()
