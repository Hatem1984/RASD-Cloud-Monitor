"""Offline synthetic fixtures only; never counted as real 44/44 evidence."""
import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import monitor
from rasd_stage2_observer_qa import (
    CAIRO,CODE_SHA,REPO,EXPECTED_CRON,expected_slots,load_config,slot_for,
    candidate,observe,audit_records)
ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/"sources_owner_daily_qa.json").read_text("utf-8"))
SETTING={"topics":[{"enabled":True,"aliases":["وزير التخطيط"],"match":"any"}],
         "sources":[{"id":f["id"],"name":f["name"],"url":f["url"],"enabled":True} for f in CONFIG["feeds"]],
         "start":"00:00","end":"22:00","scan_minutes":30,"send_at":"22:00"}
ENV={"GITHUB_REPOSITORY":REPO,"GITHUB_REF":"refs/heads/main",
     "GITHUB_EVENT_NAME":"schedule","GITHUB_EVENT_SCHEDULE":EXPECTED_CRON,
     "GITHUB_RUN_ID":"999001"}
SRC=[x["id"] for x in CONFIG["feeds"]]
DAY=date(2026,11,4)
def sample(slot="00:00",kind="QA_REAL_SLOT_OBSERVATION",status="OBSERVED_RSS_ALL_SOURCES"):
    h,m=map(int,slot.split(":"))
    start=datetime(2026,11,4,h,m+7,tzinfo=CAIRO)
    return {"schema_version":1,"kind":kind,"day_cairo":DAY.isoformat(),
       "slot_cairo":slot,
       "observed_at_utc":start.astimezone(timezone.utc).isoformat(),
       "finished_at_utc":(start+timedelta(minutes=1)).astimezone(timezone.utc).isoformat(),
       "config_version":28,"config_sha256":"a"*64,
       "code_sha":CODE_SHA,"github_run_id":"999001",
       "source_ids":SRC,"sources":[{"id":x,"status":"ok","verified_links":1,"failure_code":None} for x in SRC],
       "candidates":[],"status":status,"smtp_sent":False,"original_screenshots_verified":False}

class Stage2Observer(unittest.TestCase):
    def test_44_expected_names_and_cutoff(self):
        self.assertEqual(len(expected_slots()),44)
        self.assertEqual(expected_slots()[0],"00:00")
        self.assertEqual(expected_slots()[-1],"21:30")
        self.assertIsNone(slot_for(datetime(2026,11,4,22,1,tzinfo=CAIRO)))
    def test_smoke_is_not_coverage(self):
        r=audit_records([sample(kind="QA_SMOKE_NO_COVERAGE")],DAY,SRC,28)
        self.assertEqual(r["observed_slots"],0)
        self.assertFalse(r["complete"])
    def test_single_and_missing_43_not_complete(self):
        r=audit_records([sample()],DAY,SRC,28)
        self.assertEqual(r["observed_slots"],1)
        self.assertEqual(len(r["missing_slots"]),43)
        self.assertFalse(r["complete"])
    def test_synthetic_44_validates_aggregator_only(self):
        r=audit_records([sample(s) for s in expected_slots()],DAY,SRC,28)
        self.assertTrue(r["complete"])
        self.assertEqual(r["healthy_slots"],44)
        # This test creates NO actual GitHub artifacts or RSS observations.
    def test_failure_stays_hold_even_with_full_44(self):
        scans=[sample(s) for s in expected_slots()]
        scans[5]["sources"][3]["status"]="failed"
        r=audit_records(scans,DAY,SRC,28)
        self.assertFalse(r["complete"])
        self.assertEqual(r["failed_slots"],["02:30"])
    def test_late_receipt_cannot_backdate_slot(self):
        x=sample()
        x["observed_at_utc"]=datetime(2026,11,4,0,34,tzinfo=CAIRO).astimezone(timezone.utc).isoformat()
        r=audit_records([x],DAY,SRC,28)
        self.assertEqual(r["observed_slots"],0)
        self.assertEqual(r["rejected_records"],1)
    def test_crossed_halfhour_cannot_be_complete(self):
        x=sample()
        x["finished_at_utc"]=datetime(2026,11,4,0,31,tzinfo=CAIRO).astimezone(timezone.utc).isoformat()
        self.assertEqual(audit_records([x],DAY,SRC,28)["rejected_records"],1)
    def test_wrong_config_version_doesnt_count(self):
        x=sample();x["config_version"]=27
        self.assertEqual(audit_records([x],DAY,SRC,28)["observed_slots"],0)
    def test_probe_read_only_does_not_claim_scheduled(self):
        now=datetime(2026,11,4,12,7,tzinfo=CAIRO)
        cfg={**CONFIG,"keywords":["وزير التخطيط"]}
        m={"active_version":28,"sha256":"a"*64,
           "settings":{"topics":[{"enabled":True,"match":"any","aliases":["وزير التخطيط"]}]}}
        result=observe(mode="probe",now=now,config=cfg,manifest=m,monitor=monitor,
            inspector=lambda *_a,**_k:{"sources":[{"feed_id":x,"status":"ok","verified_links":1}
                for x in SRC],"matched_public_articles":[]},env={})
        self.assertEqual(result["status"],"OBSERVED_RSS_ALL_SOURCES")
        self.assertEqual(result["kind"],"QA_SMOKE_NO_COVERAGE")
        self.assertFalse(result["smtp_sent"])
    def test_forged_scheduled_env_rejected(self):
        cfg={**CONFIG,"keywords":["وزير التخطيط"]}
        m={"active_version":28,"sha256":"a"*64,"settings":SETTING}
        with self.assertRaisesRegex(ValueError,"untrusted_schedule_event"):
            observe(mode="scheduled",now=datetime(2026,11,4,12,7,tzinfo=CAIRO),
                config=cfg,manifest=m,monitor=monitor,
                inspector=lambda *a,**kw:{},env={"GITHUB_EVENT_NAME":"push"})
    def test_rss_original_publisher_publication_clock_required(self):
        now=datetime(2026,11,4,12,7,tzinfo=CAIRO)
        url="https://hapijournal.com/qa-planning"
        story={"id":monitor.article_id(url),"source":CONFIG["feeds"][0]["name"],
               "headline":"وزير التخطيط","url":url,
               "published":"Wed, 04 Nov 2026 12:00:00 +0200","publisher_excerpt":""}
        self.assertIsNotNone(candidate(story,{"topics":[{"enabled":True,
            "match":"any","aliases":["وزير التخطيط"]}]},now,monitor))
        story["published"]="Wed, 04 Nov 2026 12:00:00"
        with self.assertRaises(ValueError):
            candidate(story,{"topics":[{"enabled":True,"match":"any",
                "aliases":["وزير التخطيط"]}]},now,monitor)
    def test_source_manifest_authentication_rejects_unapproved_url(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"m.json";b=Path(temp)/"b.json"
            baseline=copy.deepcopy(CONFIG)
            b.write_text(json.dumps(baseline,ensure_ascii=False),encoding="utf-8")
            s=copy.deepcopy(SETTING)
            s["topics"]=[{"enabled":True,"match":"any","aliases":["وزير التخطيط"]}]*10
            s["sources"][0]["url"]="https://unapproved.invalid/feed/"
            from rasd_stage2_observer_qa import settings_digest
            m={"scope":"QA_PREVIEW_NO_SEND","schema_version":1,
               "active_version":28,"settings":s,"sha256":settings_digest(s)}
            p.write_text(json.dumps(m,ensure_ascii=False),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"source_not_approved"):
                load_config(p,b)
if __name__=="__main__":unittest.main()
