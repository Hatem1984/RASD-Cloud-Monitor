"""Authenticated AES-GCM recovery, tamper and wrong-key HOLD tests."""
import base64
import hashlib
import secrets
import shutil
import tempfile
import unittest
from pathlib import Path

from rasd_app.encrypted_backup import create_encrypted_backup,restore_encrypted_backup,MAGIC,KEY_PREFIX
from rasd_app.enterprise import EnterpriseStore
from test_rasd_enterprise_http_access import RoleHTTPAcceptance


class TestEncryptedBackup(unittest.TestCase):
    def setUp(self):
        RoleHTTPAcceptance.setUp(self)
        self.root=Path(self.tmp.name)
        self.outtemp=tempfile.TemporaryDirectory()
        self.addCleanup(self.outtemp.cleanup)
        self.backup_root=Path(self.outtemp.name)
        self.zip=self.backup_root/"encrypted-archive"/"client.rasd.enc"
        self.key=self.backup_root/"separate-secret-recovery"/"client.key"
        self.old_sha=self.report["file_sha"]
        self.state=create_encrypted_backup(self.root,self.zip,self.key)

    def test_encrypted_content_separate_key_and_verified_restored_word(self):
        body=self.zip.read_bytes()
        self.assertTrue(body.startswith(MAGIC))
        self.assertFalse(body.startswith(b"PK"))
        self.assertNotIn(self.art["title"].encode(),body)
        self.assertNotIn(self.key.read_bytes(),body)
        self.assertNotEqual(self.zip.parent,self.key.parent)
        dst=self.root/"restored-client"
        result=restore_encrypted_backup(self.zip,self.key,dst)
        self.assertTrue(result["word_sha_verified"])
        cloned=EnterpriseStore(dst,live_only=True)
        record=cloned.report(self.a,self.report["id"])
        f=cloned.secure_file(self.a,record["file_path"])
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),self.old_sha)
        self.assertEqual(len(cloned.memberships({"id":"","platform_owner":True})),2)
        # Authenticated sessions never survive a restore.
        with cloned.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],0)

    def test_wrong_key_and_tamper_do_not_create_destination(self):
        badkey=self.backup_root/"separate-secret-recovery"/"wrong.key"
        badkey.write_text(KEY_PREFIX+base64.b64encode(secrets.token_bytes(32)).decode()+"\n")
        dst=self.root/"invalid-key-target"
        with self.assertRaisesRegex(RuntimeError,"backup_authentication_failure"):
            restore_encrypted_backup(self.zip,badkey,dst)
        self.assertFalse(dst.exists())
        damaged=self.backup_root/"encrypted-archive"/"tampered.rasd.enc"
        data=bytearray(self.zip.read_bytes());data[-15]^=4
        damaged.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError,"backup_authentication_failure"):
            restore_encrypted_backup(damaged,self.key,dst)
        self.assertFalse(dst.exists())

    def test_refuse_key_same_directory_or_reuse_key(self):
        with self.assertRaisesRegex(ValueError,"key_must_be_in_separate_directory"):
            create_encrypted_backup(self.root,self.backup_root/"encrypted-archive"/"bad.rasd.enc",
                                    self.backup_root/"encrypted-archive"/"bad.key")
        with self.assertRaises(FileExistsError):
            create_encrypted_backup(self.root,self.backup_root/"encrypted-archive"/"other.rasd.enc",self.key)
        self.assertFalse((self.backup_root/"encrypted-archive"/"other.rasd.enc").exists())

    def test_active_scan_blocks_encrypted_backup(self):
        another=self.app.store.create_tenant("جهة تعمل الآن")
        sid,_=self.app.store.start_scan(another)
        with self.assertRaisesRegex(RuntimeError,"active_manual_scan_backup_hold"):
            create_encrypted_backup(self.root,self.backup_root/"encrypted-archive"/"blocked.rasd.enc",
                                    self.backup_root/"separate-secret-recovery"/"blocked.key")
        self.assertFalse((self.backup_root/"separate-secret-recovery"/"blocked.key").exists())

if __name__=="__main__":unittest.main()
