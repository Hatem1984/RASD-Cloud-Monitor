"""Independent event journal + 22:00 Cairo acceptance; ALL SYNTHETIC, no mail."""
import copy
import hashlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from rasd_event_journal import (
    CAIRO, CASConflict, JournalHold, append_event, day_sections, empty_journal,
    mark_daily_outcome, reserve_daily, validate_journal,
)


def candidate(name="a", time="2026-10-27T10:00:00+03:00", verified=True):
    event = {
        "event_id": (name * 24)[:24],
        "status": "VERIFIED_ORIGINAL" if verified else "EVIDENCE_HOLD",
        "publisher": "Verified publisher fixture",
        "headline": "خبر تجريبي عن التمويل وليس خبرًا حقيقيًا",
        "original_url": "https://example.org/test",
    }
    if verified:
        event["first_verified_at"] = time
        event["proof"] = {
            "type": "ORIGINAL_PUBLISHER_JPEG",
            "sha256": hashlib.sha256(name.encode()).hexdigest(),
            "immutable_ref": "private-evidence://qa/" + name,
            "publisher_page_match": True,
            "word_embed_digest_verified": True,
        }
    else:
        event["first_held_at"] = time
        event["proof"] = None
        event["hold_reason"] = "publisher_access_refused"
    return event


class DailyEvidenceEventJournal(unittest.TestCase):
    def store(self, state, event):
        return append_event(state, event, expected_revision=state["revision"])[0]

    def test_full_simulated_workday_independent_of_smtp(self):
        state = empty_journal()
        # 09:00 and 09:30 no news: no events and no delivery requirements.
        self.assertEqual(day_sections(state, "2026-10-27")["eligible_00_22"], [])
        first = candidate("a", "2026-10-27T10:00:00+03:00")
        second = candidate("b", "2026-10-27T11:00:00+03:00")
        state = self.store(state, first)
        # 10:30 identical replay from a redundant collector: idempotent.
        original = copy.deepcopy(state)
        repeated, outcome = append_event(state, first, expected_revision=state["revision"])
        self.assertEqual(outcome, "unchanged")
        self.assertEqual(repeated, original)
        state = self.store(state, second)
        view = day_sections(state, "2026-10-27")
        self.assertEqual([e["event_id"] for e in view["eligible_00_22"]],
                         [first["event_id"], second["event_id"]])
        self.assertEqual(len(view["late_previous_22_00"]), 0)
        self.assertEqual(len(view["held_not_deliverable"]), 0)
        # Still present even if no interval SMTP was ever called.
        self.assertNotIn("smtp_accepted", repr(state))

        daily, outcome = reserve_daily(
            state, "2026-10-27", expected_revision=state["revision"],
            one_report_sha256="a" * 64)
        self.assertEqual(outcome, "reserved")
        self.assertEqual(daily["daily"]["2026-10-27"]["eligible"], 2)
        repeated, outcome = reserve_daily(
            daily, "2026-10-27", expected_revision=daily["revision"],
            one_report_sha256="a" * 64)
        self.assertEqual(outcome, "already_reserved_or_sent")
        self.assertEqual(repeated, daily)

    def test_22_to_midnight_goes_in_next_day_separate_section(self):
        state = empty_journal()
        state = self.store(state, candidate("c", "2026-10-27T22:30:00+03:00"))
        state = self.store(state, candidate("d", "2026-10-27T23:59:00+03:00"))
        self.assertEqual(day_sections(state, "2026-10-27")["eligible_00_22"], [])
        self.assertEqual(len(day_sections(state, "2026-10-28")["late_previous_22_00"]), 2)

    def test_held_source_separated_and_not_report_eligible(self):
        state = self.store(empty_journal(), candidate("h", verified=False))
        view = day_sections(state, "2026-10-27")
        self.assertEqual(len(view["eligible_00_22"]), 0)
        self.assertEqual(len(view["held_not_deliverable"]), 1)
        with self.assertRaisesRegex(JournalHold, "held_event_cannot_claim"):
            bad = candidate("x", verified=False)
            bad["proof"] = candidate("x")["proof"]
            self.store(state, bad)

    def test_hold_to_verified_after_original_evidence(self):
        held = candidate("h", "2026-10-27T09:35:00+03:00", verified=False)
        state = self.store(empty_journal(), held)
        state = self.store(state, candidate("h", "2026-10-27T11:01:00+03:00"))
        view = day_sections(state, "2026-10-27")
        self.assertEqual(len(view["eligible_00_22"]), 1)
        self.assertEqual(len(view["held_not_deliverable"]), 0)

    def test_conflicting_duplicate_never_overwrites_evidence(self):
        event = candidate("a")
        state = self.store(empty_journal(), event)
        altered = copy.deepcopy(event)
        altered["headline"] = "عنوان مختلف"
        with self.assertRaisesRegex(JournalHold, "conflicting_or_regressed"):
            self.store(state, altered)

    def test_cas_conflict_preserves_original(self):
        state = self.store(empty_journal(), candidate("a"))
        before = copy.deepcopy(state)
        with self.assertRaises(CASConflict):
            append_event(state, candidate("b"), expected_revision=0)
        self.assertEqual(state, before)
        with self.assertRaises(CASConflict):
            reserve_daily(state, "2026-10-27", expected_revision=0,
                          one_report_sha256="b" * 64)
        self.assertEqual(state, before)

    def test_uncertain_delivery_hold_never_releases_daily_reservation(self):
        state = self.store(empty_journal(), candidate("a"))
        state, _ = reserve_daily(
            state, "2026-10-27", expected_revision=state["revision"],
            one_report_sha256="c" * 64)
        state = mark_daily_outcome(
            state, "2026-10-27", "uncertain_hold",
            expected_revision=state["revision"])
        other, result = reserve_daily(
            state, "2026-10-27", expected_revision=state["revision"],
            one_report_sha256="c" * 64)
        self.assertEqual(result, "already_reserved_or_sent")
        self.assertEqual(other, state)

    def test_inbox_cannot_be_assumed_from_reserved(self):
        state, _ = reserve_daily(
            empty_journal(), "2026-10-27", expected_revision=0,
            one_report_sha256="c" * 64)
        with self.assertRaisesRegex(JournalHold, "inbox_unverified"):
            mark_daily_outcome(state, "2026-10-27", "inbox_verified",
                               expected_revision=state["revision"])

    def test_one_zero_day_daily_reservation(self):
        state = empty_journal()
        a, res = reserve_daily(state, "2026-10-27", expected_revision=0,
                               one_report_sha256="f" * 64)
        self.assertEqual((res, a["daily"]["2026-10-27"]["eligible"]), ("reserved", 0))
        b, res = reserve_daily(a, "2026-10-27",
                               expected_revision=a["revision"],
                               one_report_sha256="f" * 64)
        self.assertEqual(res, "already_reserved_or_sent")
        self.assertEqual(a, b)

    def test_egypt_summer_and_winter_boundaries(self):
        for day, offset in (("2026-07-05", 3), ("2026-11-05", 2)):
            with self.subTest(day=day):
                instant = datetime.fromisoformat(day + "T22:00:00").replace(tzinfo=CAIRO)
                self.assertEqual(instant.utcoffset().total_seconds(), offset * 3600)
                state = self.store(empty_journal(), candidate("a", instant.isoformat()))
                # Exactly 22:00 is for the following day, not two reports.
                self.assertFalse(day_sections(state, day)["eligible_00_22"])
                tomorrow = (instant.date().toordinal() + 1)
                from datetime import date
                nextday = date.fromordinal(tomorrow).isoformat()
                self.assertEqual(len(day_sections(state, nextday)["late_previous_22_00"]), 1)

    def test_invalid_original_proof_and_naive_time_hold(self):
        for mutation in (
            lambda x: x["proof"].update({"sha256": "fake"}),
            lambda x: x.update({"first_verified_at": "2026-10-27T10:00:00"}),
            lambda x: x["proof"].update({"publisher_page_match": False}),
            lambda x: x["proof"].update({"immutable_ref": "/tmp/fragile.jpg"}),
            lambda x: x.update({"original_url": "http://example.org/test"}),
        ):
            event = candidate("a")
            mutation(event)
            with self.assertRaises(JournalHold):
                self.store(empty_journal(), event)

    def test_do_not_confuse_complete_coverage_with_two_matched_events(self):
        state = self.store(empty_journal(), candidate("a"))
        result = day_sections(state, "2026-10-27")
        self.assertIs(result["complete_source_coverage_proven"], False)
        validate_journal(state)


if __name__ == "__main__":
    unittest.main()
