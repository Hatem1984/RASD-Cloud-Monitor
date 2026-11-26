"""Stage 04 offline Word acceptance fixtures. No email, no network."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from email.utils import format_datetime
from docx import Document
from PIL import Image,ImageDraw
from rasd_hourly_word import completed_hour,build_hourly_word
from monitor import article_id

CFG=json.loads((Path(__file__).resolve().parents[1]/"sources_newsroom_active.json").read_text("utf-8"))
NOW=datetime(2026,11,26,17,7,tzinfo=timezone.utc)
START,END=completed_hour(NOW)
FEEDS=[f for f in CFG["feeds"] if f["id"]!="vetogate"]
HEALTH=[{"feed_id":f["id"],"status":"failed" if f["id"]=="vetogate" else "ok","verified_links":0} for f in CFG["feeds"]]
def row(i,stamp=None,feed=None):
    f=feed or FEEDS[i%len(FEEDS)]
    url=f"https://{f['allowed_article_hosts'][0]}/2026/11/26/{2000000+i}"
    return {"id":article_id(url),"source":f["name"],"url":url,
            "headline":f"وزارة التخطيط تعلن مشروع التنمية رقم {100+i}",
            "publisher_excerpt":"اختبار صناعي فقط",
            "published":format_datetime(stamp or START+timedelta(minutes=10,seconds=i))}
def capture(item,feeds,dest):
    im=Image.new("RGB",(1200,900),"white");d=ImageDraw.Draw(im)
    d.rectangle((0,0,1199,120),fill="#18395a")
    for i in range(12):d.rectangle((50,180+i*40,1000-i*5,197+i*40),fill="#193859")
    d.text((60,30),item["id"],fill="white")
    im.save(dest,"JPEG",quality=90)
    return {"status":"verified","sha256":hashlib.sha256(dest.read_bytes()).hexdigest()}
def full_text(doc):
    return "\n".join([p.text for p in doc.paragraphs]+[c.text for t in doc.tables for r in t.rows for c in r.cells])
class HourlyWord(unittest.TestCase):
    def build(self,rows,**kw):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        dest=Path(folder.name)/"hourly.docx"
        result=build_hourly_word(rows,CFG,HEALTH,NOW,dest,capture=kw.pop("capture",capture),**kw)
        return result,Document(dest)
    def test_0_1_3_10(self):
        for n in (0,1,3,10):
            r,d=self.build([row(i) for i in range(n)])
            self.assertEqual((r["fresh"],r["deficit"],r["publishers"]),(n,10-n,n))
            self.assertEqual(len(d.inline_shapes),n)
            self.assertIn(f"{n} أخبار موثقة من أصل 10 مستهدفة",full_text(d))
            self.assertIn("وقت فحص الرصد:",full_text(d))
            self.assertIn("vetogate",full_text(d))
            self.assertEqual(r["email_sent"],False)
            if n==0:self.assertIn("لا يثبت عدم نشر أخبار",full_text(d))
    def test_hour_boundaries_recovery_replay_cap(self):
        rows=[row(0,START),row(1,END),row(2,START-timedelta(seconds=1)),row(3,END-timedelta(seconds=1))]
        r,d=self.build(rows+[rows[0]])
        self.assertEqual(r["decisions"],["verified_in_hour","outside_completed_hour","recovery_separate","verified_in_hour","repeated_link"])
        self.assertEqual(len(d.inline_shapes),2)
        self.assertIn("مواد أقدم خارج المستهدف الساعي: 1",full_text(d))
        r,_=self.build([row(i) for i in range(12)])
        self.assertEqual(r["fresh"],10);self.assertEqual(r["counts"]["target_capacity_deferred"],2)
    def test_hold_falls_back_to_same_publisher(self):
        rows=[row(0,START+timedelta(minutes=5)),row(5,START+timedelta(minutes=15),FEEDS[0]),row(1)]
        def held(item,feeds,dest):
            if item["id"]==rows[1]["id"]:return {"status":"hold","reason":"publisher_access_refused"}
            return capture(item,feeds,dest)
        r,d=self.build(rows,capture=held)
        self.assertEqual(r["fresh"],2);self.assertEqual(r["counts"]["original_evidence_hold"],1)
        self.assertEqual(len(d.inline_shapes),2)
    def test_history_and_related_not_deleted(self):
        a={**row(0),"published_at_cairo":"2026-11-26 18:10 EET","headline":"وزارة التخطيط تعلن تفاصيل مشروع التنمية الاقتصادية والاجتماعية رقم 100"};b={**row(1),"headline":a["headline"]}
        r,_=self.build([a,b],history=[a])
        self.assertEqual(r["decisions"],["repeated_link","related_event_review_deferred"])
    def test_invalid_digest_aborts_without_output(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/"hourly.docx"
            def corrupt(item,feeds,path):
                capture(item,feeds,path);return {"status":"verified","sha256":"0"*64}
            with self.assertRaisesRegex(RuntimeError,"identity_hold"):
                build_hourly_word([row(0)],CFG,HEALTH,NOW,dest,capture=corrupt)
            self.assertFalse(dest.exists())
    def test_naive_clock_fails_and_dst_elapsed_hour(self):
        with self.assertRaises(ValueError):completed_hour(NOW.replace(tzinfo=None))
        for scan in (datetime(2026,4,23,22,7,tzinfo=timezone.utc),datetime(2026,10,29,21,7,tzinfo=timezone.utc)):
            a,b=completed_hour(scan);self.assertEqual(b-a,timedelta(hours=1))
