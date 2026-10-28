"""Safe owner rejection: never approve, execute, or create a task."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from maal.internal_actions import TaskStore

class RejectionAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbfile=Path(self.tmp.name)/"test.sqlite"
        db=sqlite3.connect(self.dbfile)
        db.executescript("""
            CREATE TABLE drafts(draft_id TEXT PRIMARY KEY,state TEXT,
                                approval_secret_hash TEXT);
            CREATE TABLE tasks(task_id TEXT,draft_id TEXT);
            CREATE TABLE audit(sequence INTEGER PRIMARY KEY AUTOINCREMENT,
               timestamp TEXT,draft_id TEXT,event TEXT,actor TEXT,
               metadata TEXT,prev_sha256 TEXT,hash_sha256 TEXT);
            INSERT INTO drafts VALUES('fpt','DRAFT',NULL);
            INSERT INTO drafts VALUES('old','EXECUTED',NULL);
            INSERT INTO tasks VALUES('old-task','old');
        """)
        db.commit();db.close()
        self.store=TaskStore.__new__(TaskStore)
        self.store.path=self.dbfile
    def query(self,sql,args=()):
        with sqlite3.connect(self.dbfile) as db:return db.execute(sql,args).fetchall()
    def test_human_rejection_is_final_and_idempotent(self):
        self.assertEqual(self.store.reject("fpt","test-owner","EDITORIAL_NOT_ACCEPTED"),"REJECTED")
        self.assertEqual(self.store.reject("fpt","test-owner","EDITORIAL_NOT_ACCEPTED"),"REJECTED")
        self.assertEqual(self.query("SELECT state FROM drafts WHERE draft_id='fpt'"),[("REJECTED",)])
        self.assertEqual(self.query("SELECT count(*) FROM tasks WHERE draft_id='fpt'"),[(0,)])
        self.assertEqual(self.query("SELECT event FROM audit WHERE draft_id='fpt'"),
                         [("HUMAN_REJECTED",)])
        self.assertEqual(self.store.verify_audit()["integrity"],"CHAIN_VERIFIED")
    def test_old_executed_task_is_never_changed_by_rejection(self):
        with self.assertRaisesRegex(ValueError,"only_pending"):
            self.store.reject("old","test-owner")
        self.assertEqual(self.query("SELECT state FROM drafts WHERE draft_id='old'"),[("EXECUTED",)])
        self.assertEqual(self.query("SELECT count(*) FROM tasks WHERE draft_id='old'"),[(1,)])
    def test_invalid_reason_or_owner_does_not_mutate(self):
        for who,reason in (("","EDITORIAL_NOT_ACCEPTED"),("owner","BYPASS")):
            with self.assertRaises(ValueError): self.store.reject("fpt",who,reason)
        self.assertEqual(self.query("SELECT state FROM drafts WHERE draft_id='fpt'"),[("DRAFT",)])

if __name__=="__main__":unittest.main()
