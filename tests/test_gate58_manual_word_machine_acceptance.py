"""Gate58: protected manual Word must never count a HOLD or today as a full day."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from gate58_manual_acceptance import stage2_manual_machine_verdict

TODAY = date(2026, 10, 19)
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/report-unified-ministry-manual.yml"


def audit(status="READY_QA_ONLY", target="2026-10-18"):
    return {
        "mode": "stage2_ministry_unified_word_ephemeral_qa",
        "target_date_cairo": target,
        "status": status,
        "coverage": "HEALTHY" if status == "READY_QA_ONLY" else "DEGRADED",
        "all_sources_healthy": status == "READY_QA_ONLY",
        "official_pagination_complete": True,
        "selected_unique_articles": 1,
        "screenshots_verified": 1,
        "screenshots_missing": 0,
        "word_created": status == "READY_QA_ONLY",
        "word_images_verified": status == "READY_QA_ONLY",
        "source_added_to_production": False,
        "production_sources_changed": False,
        "keywords_changed": False,
        "date_only_official_not_assigned_hour": True,
        "production_15_item_cap_intact": True,
        "email_sent": False,
        "scheduler_enabled": False,
        "final_report_published": False,
        "private_storage_used": False,
    }


def receipt(ready=True):
    return {
        "encrypted": True, "plaintext_artifact": False,
        "owner_review_word_included": ready,
        "owner_review_pages_encrypted": ready,
        "owner_review_page_count": 2 if ready else 0,
        "human_visual_review": False,
    }


def assess(data=None, packed=None, *, window="yesterday", today=TODAY):
    return stage2_manual_machine_verdict(
        audit() if data is None else data,
        receipt() if packed is None else packed,
        requested_window=window, today_cairo=today,
    )


class Stage2ManualMachineAcceptanceTests(unittest.TestCase):
    def test_genuine_complete_previous_cairo_day_is_machine_qa_only(self):
        self.assertEqual(assess(), "READY_QA_ONLY")

    def test_today_is_partial_not_a_second_complete_reporting_day(self):
        self.assertEqual(
            assess(audit(target="2026-10-19"), window="today"),
            "PARTIAL_QA_ONLY")

    def test_source_hold_packages_audit_only_and_never_green_report(self):
        self.assertEqual(assess(audit(status="HOLD"), receipt(False)), "HOLD")

    def test_hold_containing_word_is_refused(self):
        with self.assertRaisesRegex(ValueError, "manual_hold_contains_word"):
            assess(audit(status="HOLD"), receipt(True))

    def test_wrong_full_day_does_not_count_even_if_images_pass(self):
        for window, bad_date in (
            ("yesterday", "2026-10-17"),
            ("today", "2026-10-18"),
        ):
            with self.subTest(window=window), self.assertRaisesRegex(
                ValueError, "manual_window_audit_date_mismatch"
            ):
                assess(audit(target=bad_date), window=window)

    def test_publisher_image_missing_or_fake_owner_artifact_is_rejected(self):
        cases = [
            ({"screenshots_missing": 1}, {}),
            ({"screenshots_verified": 0}, {}),
            ({"word_images_verified": False}, {}),
            ({"all_sources_healthy": False}, {}),
            ({"official_pagination_complete": False}, {}),
            ({}, {"owner_review_word_included": False}),
            ({}, {"owner_review_pages_encrypted": False}),
            ({}, {"owner_review_page_count": 0}),
            ({}, {"human_visual_review": True}),
        ]
        for edits, receipt_edits in cases:
            with self.subTest(edits=edits, receipt=receipt_edits):
                a = audit()
                p = receipt()
                a.update(edits)
                p.update(receipt_edits)
                with self.assertRaisesRegex(
                    ValueError, "manual_ready_evidence_incomplete"
                ):
                    assess(a, p)

    def test_no_email_cron_r2_plaintext_or_scope_change_accepted(self):
        for field in (
            "email_sent", "scheduler_enabled", "final_report_published",
            "private_storage_used", "source_added_to_production",
            "production_sources_changed", "keywords_changed",
        ):
            with self.subTest(field=field):
                a = audit()
                a[field] = True
                with self.assertRaisesRegex(ValueError, "scope_violation"):
                    assess(a)
        with self.assertRaisesRegex(ValueError, "ciphertext_receipt_missing"):
            assess(packed={**receipt(), "plaintext_artifact": True})

    def test_reject_invalid_window_or_date_input(self):
        with self.assertRaisesRegex(ValueError, "manual_window_not_approved"):
            assess(window="last_month")
        with self.assertRaisesRegex(ValueError, "manual_today_cairo_invalid"):
            assess(today="2026-10-19")

    def test_real_workflow_is_manual_only_and_truthfully_gates_qa(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("github.actor == 'Hatem1984'", workflow)
        self.assertIn("RASD_MAIL_ENABLED: \"false\"", workflow)
        self.assertIn("RASD_SCHEDULER_ENABLED: \"false\"", workflow)
        self.assertIn("RASD_STAGE2_WINDOW_MODE:", workflow)
        self.assertIn('mode="$RASD_STAGE2_WINDOW_MODE"', workflow)
        self.assertNotIn('mode="${{ inputs.day }}"', workflow)
        self.assertIn("stage2_manual_machine_verdict(", workflow)
        self.assertIn("requested_window=os.environ", workflow)
        self.assertIn('datetime.now(ZoneInfo("Africa/Cairo")).date()', workflow)
        self.assertIn("if: ${{ always() }}", workflow)
        self.assertIn("RASD_STAGE2_SOURCE_OR_REPORT_HOLD_NOT_ACCEPTED", workflow)
        self.assertIn("RASD_STAGE2_PARTIAL_DAY_NOT_COMPLETE_DAY_ACCEPTANCE", workflow)
        self.assertIn("RASD_STAGE2_COMPLETE_CAIRO_DAY_MACHINE_ACCEPTED_HUMAN_REVIEW_PENDING", workflow)
        self.assertIn("path: ${{ runner.temp }}/rasd-g43-owner-encrypted.json", workflow)
        self.assertIn("retention-days: 1", workflow)
        self.assertNotIn("RASD_GMAIL_APP_PASSWORD", workflow)


if __name__ == "__main__":
    unittest.main()
