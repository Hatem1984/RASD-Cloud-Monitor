"""Offline backup/restore and report SHA acceptance, no production ledger."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timedelta,timezone

from rasd_app.enterprise import EnterpriseStore
from rasd_app.backup import create_backup,restore_backup

SOURCE="https://hapijournal.com/feed/"


class RestoreAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=EnterpriseStore(self.root/"private",live_only=True)
        self.owner=self.store.create_user("private@owner.test","private-owner-credential-123",owner=True)
        self.tid=self.store.create_tenant("جهة تجربة استرجاع حقيقية",includes=["المالية"],
                duplicate_policy="coverages")
        self.store.add_source(self.tid,"حابي",SOURCE)
        sid,_=self.store.start_scan(self.tid)
        event={"title":"وزير المالية يعلن خطة جديدة",
               "url":"https://hapijournal.com/local-qa/1",
               "publisher":"hapijournal.com",
               "published":(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()}
        with patch("rasd_app.enterprise.parse_live_feed",return_value=[event]):
            self.store.run_scan(self.tid,sid)
        art=self.store.articles(self.tid)[0]
        self.store.review(self.tid,art["id"],"private@owner.test","approved",
                          reason="تم التأكد من الرابط")
        self.report=self.store.create_report(self.tid,[art["id"]],
                     (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),
                     datetime.now(timezone.utc).isoformat())

    def test_backup_restore_isolation_sha_and_account(self):
        old=Path(self.report["file_path"])
        original=hashlib.sha256(old.read_bytes()).hexdigest()
        archive=self.root/"backups"/"private.zip"
        result=create_backup(self.root/"private",archive)
        self.assertGreaterEqual(result["files"],2)
        destination=self.root/"restored-other-instance"
        outcome=restore_backup(archive,destination)
        self.assertEqual(outcome["tenants"],1)
        clone=EnterpriseStore(destination,live_only=True)
        copied=clone.report(self.tid,self.report["id"])
        restored=clone.secure_file(self.tid,copied["file_path"])
        self.assertNotEqual(str(restored),str(old))
        self.assertEqual(hashlib.sha256(restored.read_bytes()).hexdigest(),original)
        self.assertEqual(clone.tenant(self.tid)["name"],"جهة تجربة استرجاع حقيقية")
        token,_=clone.login("private@owner.test","private-owner-credential-123")
        self.assertTrue(clone.session_user(token))
        # Reopened after another process-style Store instance:
        self.assertEqual(EnterpriseStore(destination).list_reports(self.tid)[0]["file_sha"],original)

    def test_restoring_to_non_empty_client_is_forbidden(self):
        backup=self.root/"backup.zip"
        create_backup(self.root/"private",backup)
        occupied=self.root/"occupied"
        occupied.mkdir()
        (occupied/"retain.txt").write_text("keep")
        with self.assertRaisesRegex(ValueError,"restore_destination_must_be_empty"):
            restore_backup(backup,occupied)
        self.assertEqual((occupied/"retain.txt").read_text(),"keep")

    def test_running_scan_blocks_archive(self):
        tid=self.store.create_tenant("جهة جديدة تعمل")
        sid,_=self.store.start_scan(tid)
        with self.assertRaisesRegex(RuntimeError,"active_manual_scan_backup_hold"):
            create_backup(self.root/"private",self.root/"blocked.zip")
        self.assertFalse((self.root/"blocked.zip").exists())

if __name__=="__main__":
    unittest.main()
