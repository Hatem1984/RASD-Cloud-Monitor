"""Free ciphertext-only Git transport: no R2, SMTP, real owner key or GitHub I/O."""
import base64
import json
import subprocess
import tempfile
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes

from free_private_github_backup import (
    BACKUP_BRANCH, backup_private_ciphertext, plan_local_encrypted_backup,
)


def synthetic_owner_envelope() -> bytes:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = AESGCM.generate_key(bit_length=256)
    nonce = bytes(range(12))
    wrapped = private.public_key().encrypt(
        key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                          algorithm=hashes.SHA256(), label=None))
    encrypted = AESGCM(key).encrypt(
        nonce, b"SYNTHETIC_FREE_BACKUP_TRANSPORT_ONLY",
        b"RASD-GATE43-OWNER-MINISTRY-REVIEW-v1")
    # Private key is discarded. Never put it into repository or output.
    envelope = {
        "format": "RASD_G43_OWNER_ENCRYPTED",
        "wrapped": base64.b64encode(wrapped).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(encrypted).decode(),
    }
    return json.dumps(envelope, sort_keys=True).encode("ascii")


def run_git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdin=subprocess.DEVNULL, capture_output=True)


class FreeCiphertextBackupTests(unittest.TestCase):
    def test_reject_plaintext_word_symlink_and_bad_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain = root / "plaintext.docx"
            plain.write_bytes(b"PK" * 300)
            with self.assertRaises(ValueError):
                plan_local_encrypted_backup(plain, date(2026, 10, 24))
            bad = root / "bad.json"
            bad.write_bytes(b'{"status":"READY","word":"plaintext"}')
            with self.assertRaises(ValueError):
                plan_local_encrypted_backup(bad, date(2026, 10, 24))
            good = root / "valid.json"
            good.write_bytes(synthetic_owner_envelope())
            with self.assertRaises(ValueError):
                # A completed date becomes valid tomorrow; use Cairo today
                # to exercise the deliberately rejected not-yet-completed day.
                plan_local_encrypted_backup(good, datetime.now(ZoneInfo("Africa/Cairo")).date())

    def test_real_git_offline_bare_remote_write_readback_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare = root / "private.git"
            work = root / "init"
            bare.mkdir()
            work.mkdir()
            run_git(["init", "--bare", str(bare)], cwd=root)
            run_git(["init"], cwd=work)
            run_git(["config", "user.name", "RASD test"], cwd=work)
            run_git(["config", "user.email", "rasd@test.invalid"], cwd=work)
            run_git(["checkout", "-b", "main"], cwd=work)
            (work / "README.md").write_text("Private test repo", encoding="utf-8")
            run_git(["add", "README.md"], cwd=work)
            run_git(["commit", "-m", "test baseline"], cwd=work)
            run_git(["remote", "add", "origin", bare.as_uri()], cwd=work)
            run_git(["push", "-u", "origin", "main"], cwd=work)
            source = root / "owner-encrypted.json"
            source.write_bytes(synthetic_owner_envelope())
            first = backup_private_ciphertext(
                source, day=date(2026, 10, 24), repository_url=bare.as_uri())
            self.assertTrue(first["remote_byte_identical"])
            self.assertFalse(first["original_owner_plaintext_uploaded"])
            self.assertFalse(first["owner_private_key_accessed"])
            self.assertFalse(first["new_paid_subscription"])
            self.assertFalse(first["already_present"])
            second = backup_private_ciphertext(
                source, day=date(2026, 10, 24), repository_url=bare.as_uri())
            self.assertTrue(second["already_present"])
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["object_key"], second["object_key"])
            listing = subprocess.run(
                ["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only",
                 BACKUP_BRANCH], capture_output=True, text=True, check=True)
            self.assertEqual(listing.stdout.strip(), first["object_key"])
            # The private repo default/main branch remains untouched.
            base_listing = subprocess.run(
                ["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only",
                 "main"], capture_output=True, text=True, check=True)
            self.assertEqual(base_listing.stdout.strip(), "README.md")

    def test_unapproved_remote_destination_rejected_before_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "envelope.json"
            payload.write_bytes(synthetic_owner_envelope())
            with self.assertRaises(ValueError):
                backup_private_ciphertext(
                    payload, day=date(2026, 10, 24),
                    repository_url="https://example.com/steal.git")


if __name__ == "__main__":
    unittest.main()
