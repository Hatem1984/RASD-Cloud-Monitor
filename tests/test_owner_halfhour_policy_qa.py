"""No network and no email. Synthetic screenshot fixtures are test-only, never Ministry evidence."""
import json
import hashlib
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from PIL import Image

import rasd_halfhour_policy_qa as stage

QA=Path(__file__).resolve().parent.parent
SPEC=json.loads((QA/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
SETTINGS={
    "scan_minutes":30, "send_at":"22:00",
    "sources":[{"id":s["id"],"name":s["name"],"enabled":True} for s in SPEC["feeds"]],
    "topics":[{"label":"وزير التخطيط","aliases":["وزير التخطيط"],"enabled":True,"match":"any"},
              {"label":"بنك الاستثمار القومي","aliases":["بنك الاستثمار القومي"],"enabled":True,"match":"any"}],
}
HEALTH=[{"feed_id":f["id"],"status":"ok"} for f in SPEC["feeds"]]
PUBLISHER=SPEC["feeds"][0]["name"]

def article(ident="news-a",at="2026-11-03 10:14 EET",text="وزير التخطيط يتابع مشروعًا"):
    return {"id":ident, "published_at_cairo":at,"source":PUBLISHER,
            "headline":text,"publisher_excerpt":"","url":"https://hapijournal.com/verified-original-"+ident}

class OwnerHalfhourPolicy(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
    def proof(self,item):
        p=Path(self.temp.name)/str(item["id"]+".jpg")
        Image.new("RGB",(1100,830),"#006777").save(p,format="JPEG")
        return {item["id"]:{"status":"verified","story_id":item["id"],
                           "original_url":item["url"],"screenshot_path":str(p),
                           "sha256":hashlib.sha256(p.read_bytes()).hexdigest()}}
    def plan(self,items=(),proofs=None,now=None,ledger=None,health=None,settings=None):
        return stage.plan_halfhour(settings=settings or SETTINGS,
          now=now or datetime(2026,11,3,10,37,tzinfo=stage.CAIRO),
          found=list(items),source_health=health or HEALTH,
          ledger_entries={} if ledger is None else ledger,
          original_capture_receipts={} if proofs is None else proofs)
    def test_no_news_never_sends_or_prepares_mail(self):
        r=self.plan()
        self.assertEqual(r["status"],"NO_NEW_VERIFIED_NO_SEND")
        self.assertIsNone(r["delivery_key"])
        self.assertFalse(r["smtp_allowed"])
    def test_with_one_new_original_evidence_prepare_once_only_qa(self):
        n=article()
        r=self.plan([n],self.proof(n))
        self.assertEqual(r["status"],"READY_WORD_QA_NOT_SENT")
        self.assertEqual(r["new_verified_count"],1)
        self.assertRegex(r["delivery_key"],r"^[0-9a-f]{24}$")
        self.assertFalse(r["smtp_allowed"])
        repeated=self.plan([n],self.proof(n),ledger={n["id"]:{"status":"smtp_accepted"}})
        self.assertEqual(repeated["status"],"NO_NEW_VERIFIED_NO_SEND")
        self.assertEqual(repeated["duplicate_or_reserved"],1)
    def test_reserved_uncertain_is_not_blindly_retried(self):
        n=article()
        r=self.plan([n],self.proof(n),ledger={n["id"]:{"status":"reserved"}})
        self.assertEqual(r["new_verified_count"],0)
        self.assertEqual(r["duplicate_or_reserved"],1)
        self.assertIsNone(r["delivery_key"])
    def test_no_screenshot_retains_hold_without_email(self):
        r=self.plan([article()])
        self.assertEqual(r["status"],"HOLD_EVIDENCE_NO_SEND")
        self.assertEqual(r["held_screenshots"],1)
        self.assertFalse(r["smtp_allowed"])
    def test_wrong_picture_hash_and_url_are_hold(self):
        n=article()
        broken=self.proof(n)
        broken[n["id"]]["original_url"]="https://other.example/news"
        self.assertEqual(self.plan([n],broken)["status"],"HOLD_EVIDENCE_NO_SEND")
        broken=self.proof(n)
        broken[n["id"]]["sha256"]="0"*64
        self.assertEqual(self.plan([n],broken)["status"],"HOLD_EVIDENCE_NO_SEND")
    def test_window_rejects_yesterday_after_22_and_future(self):
        cases=[article("yesterday","2026-11-02 23:50 EET"),
               article("later","2026-11-03 22:01 EET"),
               article("future","2026-11-03 14:00 EET")]
        r=self.plan(cases)
        self.assertEqual(r["held_screenshots"],0)
        self.assertEqual(r["new_verified_count"],0)
    def test_failed_source_does_not_make_coverage_complete(self):
        n=article()
        health=[{**s,"status":"failed" if s["feed_id"]=="alborsa" else "ok"} for s in HEALTH]
        r=self.plan([n],self.proof(n),health=health)
        self.assertEqual(r["coverage"],"PARTIAL")
        self.assertEqual(r["status"],"READY_WORD_QA_NOT_SENT")
    def test_unknown_missing_health_must_fail(self):
        with self.assertRaisesRegex(ValueError,"source_health_incomplete"):
            self.plan(health=HEALTH[:-1])
    def test_source_disabled_never_appears_in_results(self):
        n=article()
        config=json.loads(json.dumps(SETTINGS))
        config["sources"][0]["enabled"]=False
        health=HEALTH[1:]
        self.assertEqual(self.plan([n],self.proof(n),settings=config,health=health)["new_verified_count"],0)
    def test_no_old_or_unchanged_keyword(self):
        n=article(text="خبر زراعي لا يتصل بالتخطيط")
        self.assertEqual(self.plan([n],self.proof(n))["new_verified_count"],0)
    def test_after_22_00_no_competing_interval(self):
        n=article()
        r=self.plan([n],self.proof(n),now=datetime(2026,11,3,22,7,tzinfo=stage.CAIRO))
        self.assertEqual(r["status"],"SKIP_FINAL_CUTOFF")
    def test_rollup_only_current_day_published_and_smtp_accepted(self):
        n=article()
        old=article("prior","2026-11-02 18:10 EET")
        other=article("new-late","2026-11-03 21:45 EET")
        end=datetime(2026,11,3,22,10,tzinfo=stage.CAIRO)
        ledger={
            n["id"]:{"kind":"interval_item","status":"smtp_accepted","news":n},
            old["id"]:{"kind":"interval_item","status":"smtp_accepted","news":old},
            "reserved":{"kind":"interval_item","status":"reserved","news":other},
        }
        r=stage.plan_daily(settings=SETTINGS,report_date=date(2026,11,3),now=end,
                           ledger_entries=ledger,source_health=HEALTH)
        self.assertEqual(r["status"],"READY_DAILY_WORD_QA_NOT_SENT")
        self.assertEqual(r["count"],1)
        self.assertEqual(r["article_ids"],[n["id"]])
        self.assertFalse(r["smtp_allowed"])
    def test_final_new_original_not_earlier_sent_captured_in_digest(self):
        late=article("late","2026-11-03 21:57 EET")
        r=stage.plan_daily(settings=SETTINGS,report_date=date(2026,11,3),
                  now=datetime(2026,11,3,22,8,tzinfo=stage.CAIRO),
                  ledger_entries={},source_health=HEALTH,
                  final_new_verified=[late],final_original_receipts=self.proof(late))
        self.assertEqual(r["article_ids"],[late["id"]])
    def test_no_news_all_day_no_empty_final_email(self):
        r=stage.plan_daily(settings=SETTINGS,report_date=date(2026,11,3),
                  now=datetime(2026,11,3,22,8,tzinfo=stage.CAIRO),
                  ledger_entries={},source_health=HEALTH)
        self.assertEqual(r["status"],"NO_ACCEPTED_NEWS_NO_EMPTY_MAIL")
        self.assertEqual(r["count"],0)
    def test_daily_rollup_key_does_not_change_when_config_changes(self):
        r=stage.plan_daily(settings=SETTINGS,report_date=date(2026,11,3),
                  now=datetime(2026,11,3,22,8,tzinfo=stage.CAIRO),
                  ledger_entries={},source_health=HEALTH)
        k=r["delivery_key"]
        self.assertEqual(k,stage.digest_key("rollup:2026-11-03"))
        self.assertEqual(stage.plan_daily(settings=SETTINGS,report_date=date(2026,11,3),
                  now=datetime(2026,11,3,22,8,tzinfo=stage.CAIRO),
                  ledger_entries={k:{"status":"reserved"}},source_health=HEALTH)["status"],
                         "ALREADY_RESERVED_OR_SENT_NO_SEND")
    def test_before_cutoff_final_not_sent(self):
        r=stage.plan_daily(settings=SETTINGS,report_date=date(2026,11,3),
                  now=datetime(2026,11,3,21,59,tzinfo=stage.CAIRO),
                  ledger_entries={},source_health=HEALTH)
        self.assertEqual(r["status"],"WAIT_UNTIL_22_CAIRO_NO_SEND")
    def test_22_evening_not_in_following_day(self):
        item=article("after","2026-11-03 22:15 EET")
        self.assertFalse(stage.in_owner_day(item,date(2026,11,3),
                         datetime(2026,11,3,23,0,tzinfo=stage.CAIRO)))
        self.assertFalse(stage.in_owner_day(item,date(2026,11,4),
                         datetime(2026,11,4,10,0,tzinfo=stage.CAIRO)))
    def test_changed_owner_window_changes_halfhour_candidate(self):
        n=article()
        changed=json.loads(json.dumps(SETTINGS))
        changed["start"]="12:00"
        changed["end"]="22:00"
        rejected=self.plan([n],self.proof(n),settings=changed)
        self.assertEqual(rejected["status"],"NO_NEW_VERIFIED_NO_SEND")
        changed["start"]="00:00"
        self.assertEqual(self.plan([n],self.proof(n),settings=changed)["new_verified_count"],1)
    def test_accepted_news_survives_owner_keyword_revision_in_daily_digest(self):
        n=article()
        revised=json.loads(json.dumps(SETTINGS))
        revised["topics"]=[{"label":"آخر","aliases":["مصطلح غير وارد"],
                            "enabled":True,"match":"any"}]
        end=datetime(2026,11,3,22,9,tzinfo=stage.CAIRO)
        ledger={n["id"]:{"kind":"interval_item","status":"smtp_accepted","news":n}}
        result=stage.plan_daily(settings=revised,report_date=date(2026,11,3),
                                now=end,ledger_entries=ledger,source_health=HEALTH)
        self.assertEqual(result["count"],1)
        self.assertEqual(result["article_ids"],[n["id"]])
    def test_only_one_mail_can_be_reserved_per_half_hour_slot(self):
        first=article("a","2026-11-03 10:10 EET")
        second=article("b","2026-11-03 10:35 EET")
        first_run=self.plan([first],self.proof(first),
                            now=datetime(2026,11,3,10,36,tzinfo=stage.CAIRO))
        self.assertEqual(first_run["status"],"READY_WORD_QA_NOT_SENT")
        self.assertIn("slot_key_plus_all_article_ids",first_run["required_atomic_reservation"])
        second_run=self.plan([second],self.proof(second),
                             now=datetime(2026,11,3,10,42,tzinfo=stage.CAIRO),
                             ledger={first_run["slot_reservation_key"]:{"status":"reserved"}})
        self.assertEqual(second_run["status"],"ALREADY_INTERVAL_SLOT_RESERVED_NO_SEND")
        next_slot=self.plan([second],self.proof(second),
                             now=datetime(2026,11,3,11,2,tzinfo=stage.CAIRO),
                             ledger={first_run["slot_reservation_key"]:{"status":"smtp_accepted"}})
        self.assertEqual(next_slot["status"],"READY_WORD_QA_NOT_SENT")
if __name__=="__main__":unittest.main()
