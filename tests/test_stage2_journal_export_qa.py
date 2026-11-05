"""Fake 44 windows test exporter ONLY; never asserted real day coverage."""
import unittest
from datetime import date,datetime,timedelta,timezone
from daily_report import CAIRO
from monitor import article_id
from rasd_stage2_observer_qa import CODE_SHA,expected_slots
from rasd_stage2_journal_export_qa import reviewed_day_journal
DAY=date(2026,11,4)
SRC=["hapi","almasryalyoum","shorouk","alborsa","masrawy",
     "almessa","elbalad","vetogate","dailynewsegypt","egyptindependent",
     "egyptianstreets","skynewsarabia","inp_official"]
DIGEST="e"*64
URL="https://hapijournal.com/real-original-fixture"
ARTICLE={"id":article_id(URL),"url":URL,
         "headline":"وزير التخطيط يتابع المشروعات",
         "source":"Hapi native news RSS",
         "published_at_cairo":"2026-11-04 00:01 EET",
         "published_display_cairo":"2026-11-04 00:01",
         "publisher_excerpt":""}
def synthetic(slot):
    h,m=map(int,slot.split(":"))
    now=datetime(2026,11,4,h,m+7,tzinfo=CAIRO).astimezone(timezone.utc)
    return {"schema_version":1,"kind":"QA_REAL_SLOT_OBSERVATION",
        "day_cairo":DAY.isoformat(),"slot_cairo":slot,
        "observed_at_utc":now.isoformat(),
        "finished_at_utc":(now+timedelta(seconds=40)).isoformat(),
        "config_version":28,"config_sha256":DIGEST,"code_sha":CODE_SHA,
        "github_run_id":"99999999","source_ids":SRC,
        "sources":[{"id":x,"status":"ok","failure_code":None,
                    "verified_links":1} for x in SRC],
        "candidates":[ARTICLE] if slot=="00:00" else [],
        "status":"OBSERVED_RSS_ALL_SOURCES",
        "smtp_sent":False,"original_screenshots_verified":False}
def prepare(items):
    return reviewed_day_journal(items,DAY,SRC,28,expected_code_sha=CODE_SHA,
                               expected_config_sha256=DIGEST)
class JournalExport(unittest.TestCase):
    def test_missing_window_cannot_create_private_journal(self):
        status,doc=prepare([synthetic(x) for x in expected_slots()[:-1]])
        self.assertEqual(status["status"],"HOLD_NO_PRIVATE_JOURNAL_EXPORT")
        self.assertIsNone(doc)
        self.assertEqual(status["audit"]["missing_slots"],["21:30"])
    def test_all_synthetic_44_only_proves_conversion_contract(self):
        status,doc=prepare([synthetic(x) for x in expected_slots()])
        self.assertEqual(status["status"],"READY_PRIVATE_DAY_JOURNAL_QA_REVIEW_ONLY")
        self.assertEqual(len(doc["slots"]),44)
        self.assertEqual(len(doc["articles"]),1)
        self.assertFalse(status["smtp_sent"])
        self.assertFalse(status["private_repo_written"])
    def test_partial_source_coverage_blocks_journal(self):
        items=[synthetic(x) for x in expected_slots()]
        items[3]["sources"][4]["status"]="failed"
        status,doc=prepare(items)
        self.assertIsNone(doc)
        self.assertEqual(status["audit"]["failed_slots"],["01:30"])
if __name__=="__main__":unittest.main()
