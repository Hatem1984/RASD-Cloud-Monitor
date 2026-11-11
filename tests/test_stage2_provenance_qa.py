"""Synthetic GitHub API metadata fixtures; do NOT count as actual RSS runs."""
import copy
import unittest
from rasd_stage2_provenance_qa import (
    WORKFLOW_PATH, PRIVATE_REPO, validate_scheduled_artifact
)

def example():
    receipt = {
        "kind": "QA_REAL_SLOT_OBSERVATION",
        "day_cairo": "2026-11-05",
        "slot_cairo": "00:00",
        "github_run_id": "100012",
        "observed_at_utc": "2026-11-04T22:07:41Z",
        "finished_at_utc": "2026-11-04T22:08:43Z",
        "smtp_sent": False,
        "original_screenshots_verified": False,
    }
    artifact = {
        "name": "rasd-stage2-observation",
        "id": 200014,
        "expired": False,
        "created_at": "2026-11-04T22:09:10Z",
        "workflow_run": {"id": 100012, "head_branch": "main"},
    }
    run = {
        "id": 100012,
        "event": "schedule",
        "path": WORKFLOW_PATH,
        "head_branch": "main",
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
        "created_at": "2026-11-04T22:07:00Z",
        "repository": {"full_name": PRIVATE_REPO},
    }
    return receipt, artifact, run

class Provenance(unittest.TestCase):
    def test_valid_real_scheduled_run_contract(self):
        self.assertTrue(validate_scheduled_artifact(*example()))
    def test_manual_dispatch_cannot_become_real_slot(self):
        a,b,c = example()
        c["event"] = "workflow_dispatch"
        with self.assertRaisesRegex(ValueError, "not_approved_schedule"):
            validate_scheduled_artifact(a,b,c)
    def test_push_cannot_become_real_slot(self):
        a,b,c = example()
        c["event"] = "push"
        with self.assertRaises(ValueError):
            validate_scheduled_artifact(a,b,c)
    def test_other_workflow_cannot_become_real_slot(self):
        a,b,c = example()
        c["path"] = ".github/workflows/rasd-stage2-smoke-no-send.yml"
        with self.assertRaisesRegex(ValueError, "not_approved_schedule"):
            validate_scheduled_artifact(a,b,c)
    def test_other_repo_cannot_submit_evidence(self):
        a,b,c = example()
        c["repository"]["full_name"] = "Hatem1984/RASD-Cloud-Monitor"
        with self.assertRaises(ValueError):
            validate_scheduled_artifact(a,b,c)
    def test_rerun_rejected(self):
        a,b,c = example()
        c["run_attempt"] = 2
        with self.assertRaises(ValueError):
            validate_scheduled_artifact(a,b,c)
    def test_bad_run_id_rejected(self):
        a,b,c = example()
        a["github_run_id"] = "100013"
        with self.assertRaisesRegex(ValueError, "run_identity"):
            validate_scheduled_artifact(a,b,c)
    def test_late_queued_previous_slot_rejected(self):
        a,b,c = example()
        c["created_at"] = "2026-11-04T21:37:00Z"
        with self.assertRaisesRegex(ValueError, "late_slot"):
            validate_scheduled_artifact(a,b,c)
    def test_fabricated_receipt_timestamp_rejected(self):
        a,b,c = example()
        a["observed_at_utc"] = "2026-11-04T22:02:00Z"
        with self.assertRaisesRegex(ValueError, "out_of_order"):
            validate_scheduled_artifact(a,b,c)
    def test_expired_artifact_rejected(self):
        a,b,c = example()
        b["expired"] = True
        with self.assertRaisesRegex(ValueError, "artifact_identity"):
            validate_scheduled_artifact(a,b,c)
    def test_artifact_precedes_evidence_rejected(self):
        a,b,c = example()
        b["created_at"] = "2026-11-04T22:08:00Z"
        with self.assertRaisesRegex(ValueError, "out_of_order"):
            validate_scheduled_artifact(a,b,c)
    def test_different_day_and_timezone_rejected(self):
        a,b,c = example()
        a["day_cairo"] = "2026-11-04"
        with self.assertRaisesRegex(ValueError, "late_slot"):
            validate_scheduled_artifact(a,b,c)
    def test_smtp_contaminated_receipt_rejected(self):
        a,b,c = example()
        a["smtp_sent"] = True
        with self.assertRaisesRegex(ValueError, "not_a_real_safe_slot"):
            validate_scheduled_artifact(a,b,c)

if __name__ == "__main__":
    unittest.main()
