"""Offline 00:00–22:00 final evidence and archive gap closure.

No remote GitHub, no SMTP/IMAP or publisher webpage is contacted in these tests.
Photos are explicit synthetic JPEG test fixtures, never accepted live evidence.
"""
import hashlib,json,tempfile,unittest
from datetime import date,datetime
from pathlib import Path
from PIL import Image
from docx import Document

from monitor import article_id
import rasd_owner_daily_closeout as close
from rasd_owner_evidence_journal import new_day,add_observation,audit_day,complete_slot_names
from daily_report import CAIRO,render_docx
from cloud_proof_report import word_images_match_capture_digests

ROOT=Path(__file__).resolve().parent.parent
BASELINE=json.loads((ROOT/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
HEALTH=[{"feed_id":f["id"],"status":"ok","verified_links":12} for f in BASELINE["feeds"]]
OWNER={"topics":[{"label":"وزير التخطيط","aliases":["وزير التخطيط"],"enabled":True,"match":"any"}],
       "sources":[{"id":f["id"],"name":f["name"],"url":f["url"],"enabled":True} for f in BASELINE["feeds"]],
       "start":"00:00","end":"22:00","scan_minutes":30,"send_at":"22:00"}
DAY=date(2026,11,3)
NOW=datetime(2026,11,3,22,8,tzinfo=CAIRO)
def article(ident="one",published="2026-11-03 09:20 EET",headline="وزير التخطيط يناقش مشروعًا قوميًّا"):
    url="https://hapijournal.com/owner-closeout-"+ident
    return {"id":article_id(url),"headline":headline,"url":url,
            "source":BASELINE["feeds"][0]["name"],
            "published_at_cairo":published,
            "published_display_cairo":published[:16]+" القاهرة",
            "publisher_excerpt":""}

def make_journal(articles=None, bad_slot=None, missing=None):
    journal=new_day(DAY)
    for h in range(22):
        for m in (0,30):
            slot=f"{h:02}:{m:02}"
            if slot==missing:continue
            health=[dict(x) for x in HEALTH]
            if slot==bad_slot:health[0]["status"]="failed"
            seen=list(articles or []) if slot=="09:30" else []
            journal=add_observation(journal,now=datetime(2026,11,3,h,m+1,tzinfo=CAIRO),
                                    source_health=health,candidate_stories=seen,
                                    expected_source_ids=[f["id"] for f in BASELINE["feeds"]],
                                    config_version=17)
    return journal

class OwnerCloseout(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def fake_capture(self,story,feeds,path):
        path.parent.mkdir(parents=True,exist_ok=True)
        shade=hashlib.sha256(story["id"].encode()).digest()
        Image.new("RGB",(1200,900),(shade[0],shade[1],shade[2])).save(path,"JPEG",quality=90)
        return {"status":"verified","sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    def build(self,journal,*,discover_items=None,capture=None,ledger=None,consolidate=None):
        def discover(config,now,**kwargs):
            kwargs["source_records"].extend([dict(x) for x in HEALTH])
            return list(discover_items or [])
        return close.prepare_owner_closeout(config=BASELINE,baseline_config=BASELINE,
            owner_settings=OWNER,config_version=17,day=DAY,now=NOW,
            ledger_state=ledger or {"entries":{}},private_journal=journal,
            output=self.root,sender="qa-sender@gmail.com",
            recipient="qa-recipient@example.com",password="not-used",
            discover=discover,capture=capture or self.fake_capture,
            consolidate=consolidate or (lambda *a,**kw: self.fail("unexpected IMAP archive")))
    def test_complete_journal_44_slots_and_backlog_recovered_from_earlier_slot(self):
        old=article()
        j=make_journal([old])
        result=self.build(j,discover_items=[])
        self.assertEqual(result["status"],"READY_VERIFIED_DAILY_QA_NO_SEND")
        self.assertFalse(result["smtp_allowed"])
        self.assertEqual(result["count"],1)
        self.assertEqual(result["fresh_ids"],[old["id"]])
        doc=Document(result["word"])
        self.assertEqual(len(doc.inline_shapes),1)
        body="\n".join(p.text for p in doc.paragraphs)
        self.assertIn("التحليل الإجمالي",body)
        self.assertIn("09:20",body)
        self.assertIn("00:00",body)
        self.assertIn("22:00",body)
    def test_missing_slot_blocks_daily_delivery(self):
        r=self.build(make_journal([article()],missing="01:30"))
        self.assertEqual(r["status"],"HOLD_EVIDENCE_SLOT_COVERAGE")
        self.assertIn("01:30",r["audit"]["missing_slots"])
        self.assertFalse(list(self.root.glob("*.docx")))
    def test_failed_source_slot_blocks_daily_claim(self):
        r=self.build(make_journal([article()],bad_slot="17:00"))
        self.assertEqual(r["status"],"HOLD_EVIDENCE_SLOT_COVERAGE")
        self.assertIn("17:00",r["audit"]["failed_slots"])
    def test_original_photo_hold_blocks_all_mail_and_final_word(self):
        r=self.build(make_journal([article()],),capture=lambda *x,**kw:{"status":"hold","reason":"publisher_access_refused"})
        self.assertEqual(r["status"],"HOLD_FINAL_FRESH_ORIGINAL_IMAGE")
        self.assertFalse(list(self.root.glob("*.docx")))
    def test_no_news_means_no_daily_email(self):
        r=self.build(make_journal())
        self.assertEqual(r["status"],"NO_NEW_VERIFIED_NEWS_NO_DAILY_EMAIL")
        self.assertFalse(list(self.root.glob("*.docx")))
    def test_final_scan_catches_post_2130_article(self):
        fresh=article("late","2026-11-03 21:58 EET")
        r=self.build(make_journal(),discover_items=[fresh])
        self.assertEqual(r["count"],1)
        self.assertEqual(r["fresh_ids"],[fresh["id"]])
    def test_after_22_not_captured(self):
        late=article("too-late","2026-11-03 22:05 EET")
        r=self.build(make_journal(),discover_items=[late])
        self.assertEqual(r["status"],"NO_NEW_VERIFIED_NEWS_NO_DAILY_EMAIL")
    def test_sent_original_is_retrieved_from_archive_then_combined_with_late(self):
        sent=article("sent","2026-11-03 08:00 EET")
        fresh=article("fresh","2026-11-03 21:52 EET",headline="وزير التخطيط: اعتماد 17 مشروعًا استثماريًا جديدًا في المحافظات")
        # Sent article must have been observed during some slot.
        journal=make_journal([sent])
        ledger={"entries":{sent["id"]:{"status":"smtp_accepted","kind":"interval_item",
                             "news":sent,"accepted_at":"2026-11-03T08:30:00+00:00"}}}
        def consolidated(accepted, state, output, **kw):
            output.mkdir(parents=True,exist_ok=True)
            path=output/("daily-original-"+sent["id"]+".jpg")
            proof=self.fake_capture(sent,BASELINE["feeds"],path)
            report={"title":"QA sent Word","display_window_start":"00:00",
                    "display_window_end":"22:00","coverage":"QA",
                    "verified_links":1,
                    "articles":[{**sent,"evidence_image_path":str(path)}],
                    "sources":[],"limitations":"QA"}
            word=output/"archived.docx"
            render_docx(report,word)
            return word,[proof]
        r=self.build(journal,discover_items=[fresh],ledger=ledger,consolidate=consolidated)
        self.assertEqual(r["status"],"READY_VERIFIED_DAILY_QA_NO_SEND")
        self.assertEqual(r["count"],2)
        self.assertEqual(r["sent_archive_ids"],[sent["id"]])
        self.assertEqual(r["fresh_ids"],[fresh["id"]])
        self.assertEqual(len(Document(r["word"]).inline_shapes),2)
    def test_coverage_cannot_be_claimed_by_22_before_cutoff(self):
        old=article()
        def no_scan(*args,**kwargs):self.fail("no scan before cutoff")
        r=close.prepare_owner_closeout(config=BASELINE,baseline_config=BASELINE,
            owner_settings=OWNER,config_version=17,day=DAY,
            now=datetime(2026,11,3,21,59,tzinfo=CAIRO),
            ledger_state={"entries":{}},private_journal=make_journal([old]),
            output=self.root,sender="x@gmail.com",recipient="x@example.com",password="unused",
            discover=no_scan)
        self.assertEqual(r["status"],"WAIT_FOR_22_CAIRO")
if __name__=="__main__":unittest.main()
