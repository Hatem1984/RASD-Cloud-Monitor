import hashlib
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import tempfile
import unittest
from datetime import date
from pathlib import Path
from docx import Document
from docx.shared import Cm
from PIL import Image, ImageDraw
from daily_official_section import append_official_daily, _proofs
import scheduled_rasd as worker
DAY=date(2026,11,24)
class OfficialSectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.base=self.root/"base.docx"
        self.make_doc(self.base, self.make_image(self.root/"base.jpg","navy"),"Existing newsroom")
        self.before=self.base.read_bytes()
    def make_image(self,p,color):
        im=Image.new("RGB",(1000,700),"white")
        d=ImageDraw.Draw(im)
        for y in range(20,680,40):d.rectangle((30,y,970,y+20),fill=color)
        im.save(p,"JPEG",quality=90)
        return p
    def make_doc(self,path,img,title):
        d=Document();d.add_paragraph(title)
        if img:d.add_picture(str(img),width=Cm(12))
        d.save(path)
    def builder(self,path,*,target_date):
        img=self.make_image(path/"official.jpg","darkgreen")
        word=path/"official.docx"
        self.make_doc(word,img,"Official publisher headline")
        return word,[{"status":"verified","url":"https://mped.gov.eg/singlenews?id=7327&lang=ar","published_date_cairo":target_date.isoformat(),"headline":"Official publisher headline","image_path":str(img),"sha256":hashlib.sha256(img.read_bytes()).hexdigest()}]
    def test_preserves_base_and_appends_verified_original(self):
        path,status,n=append_official_daily(self.base,self.root,target_day=DAY,builder=self.builder)
        self.assertEqual((status,n),("VERIFIED_FIRST_PAGE",1))
        self.assertEqual(self.before,self.base.read_bytes())
        self.assertEqual(len(_proofs(path)),2)
        self.assertEqual(_proofs(path)[0],_proofs(self.base)[0])
        self.assertIn("Existing newsroom",Document(path).paragraphs[0].text)
    def test_hold_preserves_original_and_discloses_failure(self):
        def failed(*a,**kw):raise RuntimeError("official_original_hold_publisher_date_missing")
        path,status,n=append_official_daily(self.base,self.root,target_day=DAY,builder=failed)
        self.assertEqual((status,n),("HOLD",0))
        self.assertEqual(_proofs(path),_proofs(self.base))
        self.assertTrue(any("HOLD" in p.text for p in Document(path).paragraphs))
    def test_no_proven_date_match_distinct_from_hold(self):
        def empty(*a,**kw):raise RuntimeError("official_no_verified_new_original_today")
        _,status,n=append_official_daily(self.base,self.root,target_day=DAY,builder=empty)
        self.assertEqual((status,n),("NO_VERIFIED_DATE_MATCH_FIRST_PAGE",0))
    def test_wrong_digest_fails_closed(self):
        def bad(*a,**kw):
            w,r=self.builder(*a,**kw);r[0]["sha256"]="0"*64;return w,r
        path,status,n=append_official_daily(self.base,self.root,target_day=DAY,builder=bad)
        self.assertEqual((status,n),("HOLD",0));self.assertEqual(_proofs(path),_proofs(self.base))
    def test_wrong_date_fails_closed(self):
        def bad(*a,**kw):
            w,r=self.builder(*a,**kw);r[0]["published_date_cairo"]="2026-11-23";return w,r
        _,status,n=append_official_daily(self.base,self.root,target_day=DAY,builder=bad)
        self.assertEqual((status,n),("HOLD",0))
    def test_zero_news_base_accepts_official_without_reclassifying_newsroom(self):
        self.make_doc(self.base,None,"No previously accepted newsroom items")
        path,status,n=append_official_daily(self.base,self.root,target_day=DAY,builder=self.builder)
        self.assertEqual((status,n),("VERIFIED_FIRST_PAGE",1))
        self.assertEqual(len(_proofs(path)),1)
        self.assertIn("No previously accepted newsroom items",Document(path).paragraphs[0].text)


    def test_daily_scheduler_single_reservation_and_send_with_official_section(self):
        state={"entries":{}}
        ledger=MagicMock()
        ledger.read.side_effect=lambda: (state,"mock")
        def reserve(key,recipient):
            state["entries"][key]={"status":"reserved"}
            return "reserved"
        def accepted(key,receipt):
            state["entries"][key]={"status":"smtp_accepted","message_id":receipt}
        ledger.reserve.side_effect=reserve
        ledger.mark_smtp_accepted.side_effect=accepted
        def append(base,out,*,target_day):
            self.assertEqual(target_day,DAY)
            ledger.reserve.assert_not_called()
            return append_official_daily(base,out,target_day=target_day,builder=self.builder)
        def send(word,**kw):
            self.assertEqual(len(_proofs(word)),1)
            self.assertEqual(kw["key"],worker.digest_key("rollup:2026-11-24"))
            self.assertIn("لم يُقبل إرسال أخبار",kw["body_text"])
            self.assertIn("قسمًا مستقلًا للبيانات الرسمية الموثقة",kw["body_text"])
            self.assertNotIn("????",kw["body_text"])
            self.assertNotIn("ليس تقريرًا صحفيًا مصورًا",kw["body_text"])
            return "<fixture>"
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"schedule",
                "RASD_JOB_CRON":worker.DAILY_CRON,
                "RASD_DAILY_OFFICIAL_APPEND_ENABLED":"true"},clear=True), patch.object(
                worker,"require_github_scheduler"), patch.object(
                worker,"protected_credentials",return_value=("sender@example.invalid","recipient@example.invalid","offline-only",ledger)), patch.object(
                worker,"news_for_rollup",return_value=[]), patch(
                "daily_official_section.append_official_daily",side_effect=append) as section, patch.object(
                worker,"send_one_word",side_effect=send) as mail:
            now=datetime(2026,11,24,20,4,tzinfo=timezone.utc)
            result=worker.run_scheduled("rollup",now)
            again=worker.run_scheduled("rollup",now)
        self.assertEqual(result["official_section_status"],"VERIFIED_FIRST_PAGE")
        self.assertEqual(result["official_section_items"],1)
        self.assertEqual(result["items"],0)
        self.assertEqual(again["status"],"rollup_already_smtp_accepted_unconfirmed_inbox")
        section.assert_called_once()
        mail.assert_called_once()
        ledger.reserve.assert_called_once()
        ledger.mark_smtp_accepted.assert_called_once()

    def test_daily_zero_with_official_hold_body_is_arabic_and_discloses_hold(self):
        for status, phrase in [
            ("HOLD_BASE_REPORT_PRESERVED", "حُفظ التقرير الصحفي الأساسي"),
            ("HOLD", "القسم الرسمي للوزارة معلق"),
            ("NO_VERIFIED_DATE_MATCH_FIRST_PAGE", "لا يثبت ذلك عدم نشر بيانات أخرى"),
        ]:
            with self.subTest(status=status):
                ledger=MagicMock()
                ledger.read.return_value=({"entries":{}}, "mock")
                ledger.reserve.return_value="reserved"
                with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"schedule",
                        "RASD_JOB_CRON":worker.DAILY_CRON,
                        "RASD_DAILY_OFFICIAL_APPEND_ENABLED":"true"},clear=True), patch.object(
                        worker,"require_github_scheduler"), patch.object(
                        worker,"protected_credentials",return_value=("sender@example.invalid","recipient@example.invalid","offline-only",ledger)), patch.object(
                        worker,"news_for_rollup",return_value=[]), patch(
                        "daily_official_section.append_official_daily",side_effect=lambda doc,output,**kw:(doc,status,0)), patch.object(
                        worker,"send_one_word",return_value="<fixture>") as mail:
                    result=worker.run_scheduled("rollup",datetime(2026,11,24,20,4,tzinfo=timezone.utc))
                self.assertEqual(result["official_section_status"],status)
                body=mail.call_args.kwargs["body_text"]
                self.assertIn(phrase,body)
                self.assertNotIn("????",body)
                self.assertIn("لا يثبت",body)

    def test_official_time_budget_stops_before_next_read(self):
        from rasd_official_daily import build_official_daily
        with patch("rasd_official_daily.time.monotonic",side_effect=[0,0,121]), patch(
                "rasd_official_daily.discover_official_newslist",return_value=[
                    "https://mped.gov.eg/singlenews?id=7327&lang=ar"]) as listing, patch(
                "rasd_official_daily._read_original",side_effect=AssertionError("must not capture")):
            with self.assertRaisesRegex(RuntimeError,"official_time_budget_hold"):
                build_official_daily(self.root,target_date=DAY,
                    browser_factory=MagicMock(),time_budget_seconds=120)
        listing.assert_called_once()
