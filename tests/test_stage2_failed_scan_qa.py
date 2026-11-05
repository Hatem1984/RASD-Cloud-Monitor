"""Safety regression: source failures are RED in GitHub while HOLD evidence persists.

No network; all publisher failures and GitHub metadata are synthetic fixtures.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import monitor
import rasd_stage2_observer_qa as observer
from rasd_stage2_provenance_qa import PRIVATE_REPO, WORKFLOW_PATH, validate_scheduled_artifact

CONFIG=json.loads((Path(__file__).resolve().parents[1]/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
IDS=[row["id"] for row in CONFIG["feeds"]]


def receipt(status):
    return {"schema_version":1,"kind":"QA_REAL_SLOT_OBSERVATION",
            "day_cairo":"2026-11-05","slot_cairo":"00:00",
            "observed_at_utc":"2026-11-04T22:07:41Z",
            "finished_at_utc":"2026-11-04T22:08:43Z",
            "config_version":28,"config_sha256":"a"*64,
            "code_sha":observer.CODE_SHA,
            "github_run_id":"123","source_ids":IDS,
            "sources":[{"id":n,"status":"failed" if n==IDS[0] and status!="OBSERVED_RSS_ALL_SOURCES" else "ok",
                        "verified_links":0,"failure_code":"rss_invalid_xml" if n==IDS[0] else None}
                       for n in IDS],
            "candidates":[],"status":status,"smtp_sent":False,
            "original_screenshots_verified":False}


def run_metadata(conclusion):
    return {"id":123,"event":"schedule","path":WORKFLOW_PATH,
            "head_branch":"main","run_attempt":1,"status":"completed",
            "conclusion":conclusion,"created_at":"2026-11-04T22:07:00Z",
            "repository":{"full_name":PRIVATE_REPO}}


def artifact():
    return {"name":"rasd-stage2-observation","id":345,"expired":False,
            "created_at":"2026-11-04T22:09:01Z",
            "workflow_run":{"id":123,"head_branch":"main"}}


class SourceFailureHonesty(unittest.TestCase):
    def test_source_health_receipt_carries_only_allowlisted_diagnostics(self):
        rows=[{"feed_id":i,"status":"ok","verified_links":10} for i in IDS]
        rows[1]={"feed_id":IDS[1],"status":"failed","verified_links":0,
                 "failure_code":"rss_invalid_xml","xml_error_code":9,
                 "malformed_rss_length":9432,
                 "xml_input_looked_like_rss":True,
                 "identical_bad_xml_on_retry":True,
                 "error":"secret-should-not-be-emitted",
                 "url":"https://example.invalid/secret-path",
                 "raw_xml":"private-publisher-body"}
        clock=datetime(2026,11,5,12,7,tzinfo=timezone.utc)
        observed=observer.observe(mode="probe",now=clock,config=CONFIG,
            manifest={"active_version":28,"sha256":"a"*64,"settings":{"topics":[]}},
            monitor=monitor,
            inspector=lambda *args,**kwargs:{
                "sources":rows,"matched_public_articles":[]},env={})
        self.assertEqual(observed["status"],"HOLD_SOURCE_FAILURE")
        failed=observed["sources"][1]
        self.assertEqual(failed["xml_error_code"],9)
        self.assertEqual(failed["malformed_rss_length"],9432)
        self.assertTrue(failed["identical_bad_xml_on_retry"])
        self.assertNotIn("raw_xml",json.dumps(observed))
        self.assertNotIn("secret-should-not-be-emitted",json.dumps(observed))
        self.assertNotIn("url",failed)
        self.assertFalse(observed["smtp_sent"])

    def test_scheduled_failure_exits_nonzero_after_writing_receipt(self):
        for kind in ("HOLD_SOURCE_FAILURE","HOLD_SCAN_INCOMPLETE",
                     "HOLD_MISSED_OR_CROSSED_WINDOW"):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/"observation.json"
                with patch.object(observer,"load_config",return_value=(CONFIG,{})),\
                     patch.object(observer,"observe",return_value=receipt(kind)),\
                     patch.object(sys,"argv",["observer","--mode","scheduled",
                            "--manifest","unused.json","--baseline","unused.json",
                            "--out",str(output)]),redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        observer.main()
                self.assertEqual(exc.exception.code,4)
                saved=json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(saved["status"],kind)
                self.assertFalse(saved["smtp_sent"])

    def test_healthy_scheduled_receipt_remains_success(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/"observation.json"
            with patch.object(observer,"load_config",return_value=(CONFIG,{})),\
                 patch.object(observer,"observe",return_value=receipt("OBSERVED_RSS_ALL_SOURCES")),\
                 patch.object(sys,"argv",["observer","--mode","scheduled",
                        "--manifest","unused.json","--baseline","unused.json",
                        "--out",str(output)]),redirect_stdout(io.StringIO()):
                observer.main()
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"],
                             "OBSERVED_RSS_ALL_SOURCES")

    def test_failed_action_with_matching_hold_receipt_is_valid_failure_evidence(self):
        self.assertTrue(validate_scheduled_artifact(
            receipt("HOLD_SOURCE_FAILURE"),artifact(),run_metadata("failure")))

    def test_failed_action_cannot_claim_healthy_slot(self):
        with self.assertRaisesRegex(ValueError,"failed_run_without_hold_receipt"):
            validate_scheduled_artifact(
                receipt("OBSERVED_RSS_ALL_SOURCES"),artifact(),run_metadata("failure"))

    def test_previous_false_green_actions_hold_is_still_a_failed_slot(self):
        historical=receipt("HOLD_SOURCE_FAILURE")
        self.assertTrue(validate_scheduled_artifact(
            historical,artifact(),run_metadata("success")))
        audited=observer.audit_records([historical],"2026-11-05",IDS,28,
            expected_config_sha256="a"*64)
        self.assertEqual(audited["failed_slots"],["00:00"])
        self.assertFalse(audited["complete"])

    def test_false_manual_run_still_rejected(self):
        m=run_metadata("failure")
        m["event"]="workflow_dispatch"
        with self.assertRaisesRegex(ValueError,"not_approved_schedule"):
            validate_scheduled_artifact(receipt("HOLD_SOURCE_FAILURE"),artifact(),m)

if __name__=="__main__": unittest.main()
