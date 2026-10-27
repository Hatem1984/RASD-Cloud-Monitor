"""Gate F acceptance: isolated SQLite E-only internal tasks, no customer effects."""
import json
import sqlite3
import uuid
import unittest
from pathlib import Path as _Path
import os as _os
_OWNER_PROOF = _os.name == "nt" and _Path(
    r"E:\MAAL\03_REPORTS_AND_REVIEW\MAAL_GATE_E_ACCEPTANCE_20261026\MAAL-historical-signal-demo.json"
).is_file()
from pathlib import Path
from datetime import date, datetime

from maal.decision_contracts import Evidence
from maal.internal_actions import TaskStore


QA = Path(r"E:\MAAL\04_HISTORICAL_QA\MAAL_GATE_F_TEST_20261027")
QA.mkdir(parents=True,exist_ok=True)

@unittest.skipUnless(_OWNER_PROOF, "Owner-only E evidence needed; no fabricated CI provenance")
class AuthorizedTaskAcceptance(unittest.TestCase):
    def setUp(self):
        self.file=QA/("task_"+uuid.uuid4().hex+".sqlite")
        self.store=TaskStore(self.file)
        from maal_web.server import get_case
        case=get_case()  # gated by original owner-local JPEG SHA and Gate D contract
        self.evidence=Evidence(
            evidence_id=case["evidence_id"],publisher=case["publisher"],
            original_url=case["original_url"],claim=case["finding"],
            published_at=date.fromisoformat(case["published_day"]),
            observed_at=datetime.fromisoformat(case["observed_at"]),
            original_page_sha256=case["evidence_digest"],
            status=case["verification_status"]
        )
        self.description="متابعة القرار الرسمي لمشروعات البنية التحتية — اختبار داخلي فقط"
        self.key="qa-"+uuid.uuid4().hex

    def draft(self):
        return self.store.create_draft(self.evidence,self.description,self.key)

    def test_never_executes_without_approval(self):
        draft=self.draft()
        with self.assertRaisesRegex(PermissionError,"human_approval_required"):
            self.store.execute(draft)
        self.assertEqual(self.store.verify_audit()["internal_tasks"],0)

    def test_rejects_bad_secret_without_approval(self):
        draft=self.draft()
        secret=self.store.issue_owner_challenge(draft)
        with self.assertRaisesRegex(PermissionError,"approval_challenge_invalid"):
            self.store.approve(draft,"OWNER","wrong-owner-code")
        with self.assertRaises(PermissionError):
            self.store.execute(draft)
        self.assertEqual(self.store.verify_audit()["internal_tasks"],0)
        # Invalid attempt must NOT consume the actual operator's challenge
        self.store.approve(draft,"OWNER",secret)
        self.assertTrue(self.store.execute(draft))

    def test_rejects_unauthorized_role(self):
        draft=self.draft()
        secret=self.store.issue_owner_challenge(draft)
        with self.assertRaisesRegex(PermissionError,"reviewer_role_not_allowed"):
            self.store.approve(draft,"AI_PLANNER",secret)
        with self.assertRaises(PermissionError):
            self.store.execute(draft)

    def test_evidence_first_no_self_attested_approval(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError,"unverified_evidence"):
            self.store.create_draft(replace(self.evidence,status="HOLD"),self.description,self.key)

    def test_same_key_same_draft_but_different_payload_rejected(self):
        draft=self.draft()
        self.assertEqual(self.draft(),draft)
        with self.assertRaisesRegex(ValueError,"idempotency_key_collision"):
            self.store.create_draft(self.evidence,"مهمة أخرى",self.key)

    def test_approved_then_executes_once_and_audit_proves_it(self):
        draft=self.draft()
        challenge=self.store.issue_owner_challenge(draft)
        self.store.approve(draft,"OWNER",challenge)
        first=self.store.execute(draft)
        second=self.store.execute(draft)
        self.assertEqual(first,second)
        result=self.store.verify_audit()
        self.assertEqual(result["internal_tasks"],1)
        self.assertEqual(result["integrity"],"CHAIN_VERIFIED")
        with self.store.db() as db:
            events=[r["event"] for r in db.execute("SELECT event FROM audit ORDER BY sequence")]
        self.assertEqual(events.count("INTERNAL_TASK_EXECUTED"),1)

    def test_failure_injection_records_audit_and_allows_safe_retry(self):
        draft=self.draft()
        secret=self.store.issue_owner_challenge(draft)
        self.store.approve(draft,"OWNER",secret)
        with self.assertRaisesRegex(RuntimeError,"injected_execution_failure"):
            self.store.execute(draft,inject_failure=True)
        self.assertEqual(self.store.verify_audit()["internal_tasks"],0)
        result=self.store.execute(draft)
        self.assertTrue(result)
        self.assertEqual(self.store.verify_audit()["internal_tasks"],1)

    def test_audit_append_only_and_detects_modification(self):
        draft=self.draft()
        self.assertEqual(self.store.verify_audit()["integrity"],"CHAIN_VERIFIED")
        with self.assertRaises(sqlite3.DatabaseError):
            with self.store.db() as db:
                db.execute("DELETE FROM audit WHERE draft_id=?",(draft,))
        self.assertEqual(self.store.verify_audit()["integrity"],"CHAIN_VERIFIED")

if __name__=="__main__":
    unittest.main(verbosity=2)
