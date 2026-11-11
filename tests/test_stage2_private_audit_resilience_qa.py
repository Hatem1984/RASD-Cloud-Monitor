"""Offline private artifact audit fixtures; no actual GitHub calls or delivery."""
import io
import json
import zipfile
import unittest
from datetime import date
from unittest.mock import patch
import rasd_stage2_artifacts_audit_qa as audit

DAY=date(2026,11,5)
def zip_receipt(run_id):
    data=json.dumps({"github_run_id":str(run_id),
       "kind":"QA_REAL_SLOT_OBSERVATION","day_cairo":DAY.isoformat()}).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w") as archive:
        archive.writestr("observation.json",data)
    return buffer.getvalue()
def record(run_id):
    return {"id":run_id+500,"name":"rasd-stage2-observation",
            "expired":False,"created_at":"2026-11-05T12:01:00Z",
            "size_in_bytes":900,
            "workflow_run":{"id":run_id,"head_branch":"main"}}

class PrivateArtifactResilience(unittest.TestCase):
    def test_one_untrusted_artifact_does_not_hide_valid_runs(self):
        records=[record(11),record(12)]
        def get(path,token):
            if path.startswith("/actions/artifacts?"):
                return json.dumps({"artifacts":records}).encode()
            if path.endswith("/zip"):
                run=int(path.split("/")[3])-500
                return zip_receipt(run)
            if path.startswith("/actions/runs/"):
                return json.dumps({"id":int(path.rsplit("/",1)[1])}).encode()
            raise AssertionError(path)
        def verify(receipt,artifact,run):
            if run["id"]==11:raise ValueError("qa_provenance_invalid")
            return True
        with patch.object(audit,"_get",side_effect=get),patch.object(
                audit,"validate_scheduled_artifact",side_effect=verify):
            valid,rejected=audit.read_private_artifacts("a"*20,DAY)
        self.assertEqual([int(x["github_run_id"]) for x in valid],[12])
        self.assertEqual(rejected,[511])
    def test_wrong_receipt_run_identity_is_marked_rejected(self):
        with patch.object(audit,"_get",side_effect=lambda p,t:
            json.dumps({"artifacts":[record(11)]}).encode()
            if p.startswith("/actions/artifacts?") else
            zip_receipt(9)):
            valid,rejected=audit.read_private_artifacts("a"*20,DAY)
        self.assertEqual(valid,[])
        self.assertEqual(rejected,[511])
    def test_corrupted_archive_is_hold_not_crash(self):
        with patch.object(audit,"_get",side_effect=lambda p,t:
            json.dumps({"artifacts":[record(11)]}).encode()
            if p.startswith("/actions/artifacts?") else
            b"not-a-zip"):
            valid,rejected=audit.read_private_artifacts("a"*20,DAY)
        self.assertEqual(valid,[])
        self.assertEqual(rejected,[511])
    def test_invalid_json_archive_is_hold_not_crash(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,"w") as archive:
            archive.writestr("observation.json",b"{not valid json")
        with patch.object(audit,"_get",side_effect=lambda p,t:
            json.dumps({"artifacts":[record(11)]}).encode()
            if p.startswith("/actions/artifacts?") else buffer.getvalue()):
            valid,rejected=audit.read_private_artifacts("a"*20,DAY)
        self.assertEqual(valid,[])
        self.assertEqual(rejected,[511])
    def test_after_midnight_utc_artifact_still_eligible_for_previous_cairo_day(self):
        late=record(15)
        late["created_at"]="2026-11-06T00:20:00Z"
        def response(path,token):
            if path.startswith("/actions/artifacts?"):
                return json.dumps({"artifacts":[late]}).encode()
            if path.endswith("/zip"):
                return zip_receipt(15)
            return b'{"id":15}'
        with patch.object(audit,"_get",side_effect=response),patch.object(audit,
            "validate_scheduled_artifact",return_value=True):
            # Fake API run data is not correct; only the date filtering
            # behavior is under test, and separate provenance tests cover it.
            valid,rejected=audit.read_private_artifacts("a"*20,DAY)
        self.assertEqual(rejected,[])
        self.assertEqual(len(valid),1)
    def test_no_artifacts_keeps_no_evidence(self):
        with patch.object(audit,"_get",return_value=b'{"artifacts":[]}'):
            valid,rejected=audit.read_private_artifacts("a"*20,DAY)
        self.assertEqual(valid,[])
        self.assertEqual(rejected,[])
if __name__=="__main__":unittest.main()
