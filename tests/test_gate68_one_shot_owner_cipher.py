"""Gate68: bounded owner-only encrypted report capture, zero production.

These tests are synthetic and NEVER constitute human visual review.
"""
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gate68_one_shot_encrypted_owner_day19 import (
    EXPECTED_MAIN_BASE, EXPECTED_BRANCH, validate_one_shot_scope,
    verify_cipher_only,
)

CAIRO = ZoneInfo("Africa/Cairo")


class Gate68OneShotAcceptanceSecurityTests(unittest.TestCase):
    def test_same_exact_owner_branch_base_completed_day(self):
        day = validate_one_shot_scope(
            datetime(2026, 10, 20, 19, 0, tzinfo=CAIRO),
            actor="Hatem1984", ref=EXPECTED_BRANCH,
            original_main_base=EXPECTED_MAIN_BASE,
        )
        self.assertEqual(day, date(2026, 10, 19))

    def test_one_day_later_cannot_replay_19_october(self):
        with self.assertRaisesRegex(ValueError, "safe_window"):
            validate_one_shot_scope(
                datetime(2026, 10, 21, 0, 1, tzinfo=CAIRO),
                actor="Hatem1984", ref=EXPECTED_BRANCH,
                original_main_base=EXPECTED_MAIN_BASE,
            )

    def test_prior_day_and_unaware_clock_refused(self):
        for dt in (datetime(2026, 10, 19, 12, tzinfo=CAIRO),
                   datetime(2026, 10, 20, 12)):
            with self.subTest(now=str(dt)), self.assertRaises(ValueError):
                validate_one_shot_scope(dt, actor="Hatem1984",
                                        ref=EXPECTED_BRANCH,
                                        original_main_base=EXPECTED_MAIN_BASE)

    def test_spoofed_actor_or_branch_or_base_refused(self):
        now = datetime(2026, 10, 20, 19, tzinfo=CAIRO)
        for actor, ref, base in (
            ("SomeOtherUser", EXPECTED_BRANCH, EXPECTED_MAIN_BASE),
            ("Hatem1984", "refs/heads/main", EXPECTED_MAIN_BASE),
            ("Hatem1984", EXPECTED_BRANCH, "0" * 40),
        ):
            with self.subTest(actor=actor,ref=ref,base=base):
                with self.assertRaisesRegex(ValueError, "authenticated_owner"):
                    validate_one_shot_scope(
                        now, actor=actor, ref=ref, original_main_base=base
                    )

    def test_only_approved_ciphertext_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "owner.json"
            dest.write_text(json.dumps({
                "format": "RASD_G43_OWNER_ENCRYPTED",
                "ciphertext": "random-ciphertext", "nonce": "nonce", "wrapped": "key",
            }), encoding="ascii")
            self.assertGreater(verify_cipher_only(dest), 40)
            for extra in ({"plaintext_word": "very private"},
                          {"artifact_sha256": "aa"}):
                with self.subTest(extra=extra):
                    payload = json.loads(dest.read_text())
                    payload.update(extra)
                    dest.write_text(json.dumps(payload))
                    with self.assertRaisesRegex(ValueError, "exclusive"):
                        verify_cipher_only(dest)
                    for field in extra:
                        payload.pop(field)
                    dest.write_text(json.dumps(payload))

    def test_workflow_requires_owner_and_no_transport_or_plaintext_upload(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/gate68-owner-encrypted-day19-once.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("github.actor == 'Hatem1984'", workflow)
        self.assertIn("refs/heads/gate68-one-shot-owner-encrypted-day19", workflow)
        self.assertIn("RASD-GATE68-CIPHER-ONCE", workflow)
        self.assertIn("git merge-base HEAD", workflow)
        self.assertIn("rasd-g43-owner-encrypted.json", workflow)
        self.assertIn("retention-days: 1", workflow)
        self.assertIn("if: ${{ always() }}", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("gmail", workflow.lower())
        self.assertNotIn("workflow_dispatch", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("RASD-Unified-*.docx", workflow)

    def test_one_shot_helper_never_sends_or_decrypts_and_cleans_temp(self):
        f=(Path(__file__).resolve().parents[1]/
           "gate68_one_shot_encrypted_owner_day19.py").read_text()
        self.assertIn("TemporaryDirectory(", f)
        self.assertIn("pack_owner_review(", f)
        self.assertIn("rendered_word_preflight(", f)
        self.assertIn("owner_bound_stage2_mime_check(", f)
        for word in (
            "smtplib", "gmail_submit(", "unpack_owner_review(",
            "PrivateGitHubLedger", "boto3", "requests.post(",
        ):
            self.assertNotIn(word, f)


if __name__ == "__main__":
    unittest.main()
