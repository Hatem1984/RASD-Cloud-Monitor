"""New owner-requested hourly calendar while retaining archived 30m tests.

All mocked observations are only offline verification, NEVER 22 real runs.
"""
import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,date,timezone
from rasd_stage2_observer_qa import (
    CAIRO,HOURLY_CRON,slot_for,expected_slots,load_config,
    audit_records,observe,CODE_SHA,candidate)
from rasd_stage2_provenance_qa import validate_scheduled_artifact,WORKFLOW_PATH,PRIVATE_REPO
from rasd_owner_evidence_journal import (
    complete_slot_names,new_day,add_observation,audit_day)
from rasd_stage2_journal_export_qa import reviewed_day_journal
from rasd_hourly_expansion_qa import deduplicate_publisher_stories
import monitor
ROOT=Path(__file__).resolve().parents[1]
B=json.loads((ROOT/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
IDS=[x["id"] for x in B["feeds"]]
DAY=date(2026,11,6)
def record(hour,minute=7):
    start=datetime(2026,11,6,hour,minute,tzinfo=CAIRO)
    return {"schema_version":1,"kind":"QA_REAL_SLOT_OBSERVATION",
        "day_cairo":DAY.isoformat(),"slot_cairo":f"{hour:02d}:00",
        "scan_minutes":60,"observed_at_utc":start.astimezone(timezone.utc).isoformat(),
        "finished_at_utc":(start+timedelta(minutes=1)).astimezone(timezone.utc).isoformat(),
        "config_version":29,"config_sha256":"b"*64,"code_sha":CODE_SHA,
        "github_run_id":"9000","source_ids":IDS,
        "sources":[{"id":x,"status":"ok","verified_links":1} for x in IDS],
        "candidates":[],"status":"OBSERVED_RSS_ALL_SOURCES",
        "smtp_sent":False,"original_screenshots_verified":False}
def audit(items):
    return audit_records(items,DAY,IDS,29,scan_minutes=60,
                         expected_config_sha256="b"*64)
class HourlyScheduleAcceptance(unittest.TestCase):
    def test_hourly_schedule_22_and_legacy_44_archived(self):
        self.assertEqual(HOURLY_CRON,"7 0-21 * * *")
        self.assertEqual(len(expected_slots(60)),22)
        self.assertEqual(expected_slots(60)[-1],"21:00")
        self.assertEqual(len(expected_slots(30)),44)
        self.assertEqual(len(complete_slot_names(60)),22)
        self.assertEqual(len(complete_slot_names()),44)
    def test_actual_37min_belongs_same_hour_not_new_slot(self):
        self.assertEqual(slot_for(datetime(2026,11,6,3,37,tzinfo=CAIRO),60),"03:00")
    def test_current_owner_manifest_can_migrate_to_hourly_without_losing_sources(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"m.json";b=Path(d)/"baseline.json"
            # Synthetic settings only. Never require a private QA manifest
            # file or owner data that does not exist on GitHub CI runners.
            settings={"sources":[{"id":f["id"],"name":f["name"],
                         "url":f["url"],"enabled":True} for f in B["feeds"]],
                     "topics":[{"enabled":True,"match":"any",
                                "aliases":["وزارة التخطيط"]} for _ in range(10)],
                     "start":"00:00","end":"22:00",
                     "scan_minutes":60,"send_at":"22:00"}
            from rasd_stage2_observer_qa import settings_digest
            original={"schema_version":1,"scope":"QA_PREVIEW_NO_SEND",
                      "active_version":29,"settings":settings,
                      "sha256":settings_digest(settings)}
            p.write_text(json.dumps(original,ensure_ascii=False),encoding="utf-8")
            b.write_text(json.dumps(B,ensure_ascii=False),encoding="utf-8")
            cfg,manifest=load_config(p,b)
            self.assertEqual(cfg["scan_minutes"],60)
            self.assertEqual(len(cfg["feeds"]),13)
            self.assertEqual(manifest["active_version"],29)
    def test_scheduled_hourly_only_original_event(self):
        m={"active_version":29,"sha256":"b"*64,
           "settings":{"topics":[]}}
        env={"GITHUB_REPOSITORY":"Hatem1984/RASD-Pilot",
             "GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"schedule",
             "GITHUB_EVENT_SCHEDULE":HOURLY_CRON,"GITHUB_RUN_ID":"9000"}
        cfg={**B,"scan_minutes":60,"keywords":[]}
        now=datetime(2026,11,6,3,7,tzinfo=CAIRO)
        x=observe(mode="scheduled",now=now,config=cfg,manifest=m,monitor=monitor,
             inspector=lambda *a,**kw:{"sources":[{"feed_id":i,"status":"ok","verified_links":1} for i in IDS],
                                       "matched_public_articles":[]},env=env)
        self.assertEqual(x["slot_cairo"],"03:00")
        self.assertEqual(x["scan_minutes"],60)
        self.assertFalse(x["smtp_sent"])
        with self.assertRaisesRegex(ValueError,"untrusted_schedule_event"):
            observe(mode="scheduled",now=now,config=cfg,manifest=m,monitor=monitor,
              inspector=lambda *_a,**kw:{},env={**env,"GITHUB_EVENT_SCHEDULE":"7,37 0-21 * * *"})
    def test_all_22_synthetic_rows_only_validate_hourly_auditor(self):
        outcome=audit([record(h) for h in range(22)])
        self.assertEqual(outcome["expected_slots"],22)
        self.assertTrue(outcome["complete"])
        self.assertEqual(outcome["healthy_slots"],22)
    def test_missing_one_hour_is_a_real_hold(self):
        outcome=audit([record(h) for h in range(21)])
        self.assertFalse(outcome["complete"])
        self.assertEqual(outcome["missing_slots"],["21:00"])
    def test_legacy_halfhour_receipt_rejected_from_new_daily_accounting(self):
        old=record(3,37)
        old["scan_minutes"]=30
        old["slot_cairo"]="03:30"
        outcome=audit([old])
        self.assertFalse(outcome["complete"])
        self.assertEqual(outcome["rejected_records"],1)
    def test_source_failure_stays_hold_in_hourly(self):
        rows=[record(h) for h in range(22)]
        rows[4]["sources"][2]["status"]="failed"
        rows[4]["status"]="HOLD_SOURCE_FAILURE"
        outcome=audit(rows)
        self.assertEqual(outcome["failed_slots"],["04:00"])
        self.assertFalse(outcome["complete"])
    def test_hourly_receipt_provenance_uses_hour_clock(self):
        r=record(3)
        r["github_run_id"]="8001"
        r["observed_at_utc"]="2026-11-06T01:07:40Z"
        r["finished_at_utc"]="2026-11-06T01:08:40Z"
        art={"name":"rasd-stage2-observation","id":8100,
             "expired":False,"created_at":"2026-11-06T01:09:00Z",
             "workflow_run":{"id":8001,"head_branch":"main"}}
        run={"id":8001,"event":"schedule","path":WORKFLOW_PATH,
             "head_branch":"main","run_attempt":1,
             "status":"completed","conclusion":"success",
             "created_at":"2026-11-06T01:07:00Z",
             "repository":{"full_name":PRIVATE_REPO}}
        self.assertTrue(validate_scheduled_artifact(r,art,run))
    def test_hourly_journal_export_matches_new_slot_calendar(self):
        rows=[record(h) for h in range(22)]
        status,doc=reviewed_day_journal(rows,DAY,IDS,29,
             expected_code_sha=CODE_SHA,expected_config_sha256="b"*64,
             scan_minutes=60)
        self.assertEqual(status["slots"],22)
        self.assertEqual(audit_day(doc,DAY,IDS,scan_minutes=60)["expected_slots"],22)
        self.assertTrue(audit_day(doc,DAY,IDS,scan_minutes=60)["complete"])
    def test_verified_publisher_timestamp_survives_for_crosspublisher_dedup(self):
        title="وزير التخطيط يبحث المشروعات الاستثمارية في المحافظات"
        url="https://hapijournal.com/example-test"
        item={"id":monitor.article_id(url),"headline":title,"url":url,
              "published":"Fri, 06 Nov 2026 12:02:00 +0200",
              "source":"Hapi native news RSS","publisher_excerpt":""}
        saved=candidate(item,{"topics":[{"enabled":True,"match":"any","aliases":["وزير التخطيط"]}]},
                 datetime(2026,11,6,12,7,tzinfo=CAIRO),monitor)
        self.assertTrue(saved["published_at_utc"].endswith("+00:00"))
        self.assertEqual(len(deduplicate_publisher_stories([saved])),1)
if __name__=="__main__":unittest.main()
