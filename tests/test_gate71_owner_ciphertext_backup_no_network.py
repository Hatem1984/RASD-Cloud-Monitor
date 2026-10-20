"""Gate71: synthetic owner AES envelope private-backup / restore integrity tests.

There is NO real owner ciphertext, RSA private key, R2 token, bucket,
HTTP client, public artifact, Gmail recipient or production write here.
"""
from __future__ import annotations

import base64
import json
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gate71_owner_ciphertext_backup_no_network import (
    check_owner_ciphertext, prepare_private_ciphertext_backup,
    verify_private_ciphertext_roundtrip,
)


DAY = date(2026, 10, 17)


def synthetic_envelope(*, alternate=False):
    wrapped = bytes([7]) * 384
    nonce = bytes(range(12))
    cipher = bytes([8 if alternate else 9]) * 120
    return json.dumps({
        "format": "RASD_G43_OWNER_ENCRYPTED",
        "nonce": base64.b64encode(nonce).decode(),
        "wrapped": base64.b64encode(wrapped).decode(),
        "ciphertext": base64.b64encode(cipher).decode(),
    },sort_keys=True).encode()


class CiphertextR2DryRunTests(unittest.TestCase):
    def test_owner_ciphertext_only_plan_has_no_cloud_side_effect(self):
        payload=synthetic_envelope()
        plan=prepare_private_ciphertext_backup(payload,day=DAY)
        self.assertEqual(plan["status"],
                         "ENCRYPTED_OWNER_R2_NO_NETWORK_PREFLIGHT_ONLY")
        self.assertEqual(plan["cairo_day"],DAY.isoformat())
        self.assertTrue(plan["object_key"].startswith(
            "rasd/owner-ciphertext/2026/10/2026-10-17/"))
        self.assertFalse(plan["object_uploaded"])
        self.assertFalse(plan["plaintext_uploaded"])
        self.assertFalse(plan["private_key_used"])
        self.assertFalse(plan["production_approved"])
        self.assertFalse(plan["email_sent"])

    def test_exact_synthetic_bytes_roundtrip_local_only(self):
        b=synthetic_envelope()
        plan=prepare_private_ciphertext_backup(b,day=DAY)
        local=verify_private_ciphertext_roundtrip(plan,b,bytes(b))
        self.assertTrue(local["bytes_identical"])
        self.assertFalse(local["r2_used"])
        self.assertFalse(local["remote_restore_verified"])
        self.assertFalse(local["owner_decryption_performed"])

    def test_swap_to_other_valid_encrypted_envelope_rejected(self):
        b=synthetic_envelope()
        p=prepare_private_ciphertext_backup(b,day=DAY)
        alternate=synthetic_envelope(alternate=True)
        check_owner_ciphertext(alternate)
        with self.assertRaisesRegex(ValueError,"identity_mismatch"):
            verify_private_ciphertext_roundtrip(p,b,alternate)

    def test_modified_expected_payload_rejected(self):
        b=synthetic_envelope()
        p=prepare_private_ciphertext_backup(b,day=DAY)
        with self.assertRaisesRegex(ValueError,"identity_mismatch"):
            verify_private_ciphertext_roundtrip(p,synthetic_envelope(alternate=True),
                                                synthetic_envelope(alternate=True))

    def test_reject_plaintext_docx_and_invalid_envelopes(self):
        source=json.loads(synthetic_envelope())
        for payload in [
            b"PK" + b"fake word bytes"*300,
            b'{"word":"EXPOSED"}'*100,
            b"\xff"*500,
            json.dumps(dict(source, format="FAKE")).encode(),
            json.dumps(dict(source, plaintext_docx="leaked")).encode(),
            json.dumps(dict(source, nonce="not-base64")).encode(),
            json.dumps(dict(source, wrapped="bad")).encode(),
            json.dumps(dict(source, ciphertext="")).encode(),
            b"{" + b"x"*8_000_001 + b"}",
        ]:
            with self.subTest(size=len(payload)), self.assertRaises(ValueError):
                check_owner_ciphertext(payload)

    def test_current_and_future_day_not_accepted(self):
        today=datetime.now(ZoneInfo("Africa/Cairo")).date()
        for day in (today,date(2099,1,1),"2026-10-17",None):
            with self.subTest(day=day), self.assertRaisesRegex(ValueError,
                                                               "completed_cairo_day"):
                prepare_private_ciphertext_backup(synthetic_envelope(),day=day)

    def test_forged_plan_production_true_refused(self):
        b=synthetic_envelope()
        p=prepare_private_ciphertext_backup(b,day=DAY)
        p["production_approved"]=True
        with self.assertRaisesRegex(ValueError,"plan_not_safe"):
            verify_private_ciphertext_roundtrip(p,b,b)

    def test_no_live_r2_or_gmail_network_adapters(self):
        code=(Path(__file__).resolve().parents[1] /
              "gate71_owner_ciphertext_backup_no_network.py").read_text()
        for banned in ("boto3","smtplib","requests.","urlopen(",
                       "R2_ACCESS_KEY","R2_SECRET","send_message(",
                       "rsa.decrypt(","AESGCM.decrypt("):
            self.assertNotIn(banned,code)


if __name__=="__main__":
    unittest.main()
