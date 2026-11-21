"""End-to-end NO SEND: approved-source synthetic original pictures -> real hourly Word.

Exercises the real report builder, exact JPEG SHA proof and Word article/URL
order (not a mocked document or Gmail transport). All headlines, images and
domains use deliberate test fixtures only; no real publisher screenshots.
"""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from docx import Document
from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from monitor import article_id
from scheduled_rasd import prepare_source_limited_verified_word

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"sources_newsroom_active.json").read_text("utf-8"))


def prepared_news(count=3):
    items=[]
    for i,feed in enumerate(CFG["feeds"][:count]):
        url=f"https://{feed['allowed_article_hosts'][0]}/2026/11/21/fixture-real-shaped-{i+1}"
        items.append({
            "id":article_id(url),
            "headline":f"وزارة التخطيط تتابع مشروع التنمية المختلف رقم {i+11}",
            "publisher_excerpt":"اختبار Word صناعي محلي لا يمثل تغطية حقيقية",
            "source":feed["name"],"url":url,
            "published_at_cairo":f"2026-11-21 18:{i+10:02d} EET",
            "published_display_cairo":f"٢١ نوفمبر ٢٠٢٦ الساعة ١٨:{i+10:02d}",
            "published_utc":f"2026-11-21T16:{i+10:02d}:00+00:00",
            "hourly_publication_bucket":"within_previous_hour",
        })
    return items


def synthetic_capture(article, feeds, destination):
    serial=next(i for i,f in enumerate(feeds)
                if f["name"]==article["source"])
    img=Image.new("RGB",(1200,1000),"white")
    draw=ImageDraw.Draw(img)
    draw.rectangle((0,0,1199,130),fill=(10,31,65))
    draw.rectangle((55,165,1150,220),fill=(50+serial*15,100,145))
    for k in range(14):
        draw.rectangle((70,255+k*39,1000-(k%3)*41,265+k*39),
                       fill=(35,65+serial*14,155))
    draw.rectangle((220+serial*43,740,600,890),
                   fill=(50+serial*20,120,140))
    img.save(destination,format="JPEG",quality=89)
    return {"status":"verified",
            "sha256":hashlib.sha256(Path(destination).read_bytes()).hexdigest()}


class ActualHourlyWordWithPartialOriginals(unittest.TestCase):
    def test_three_authenticated_publisher_ids_three_jpeg_drawings_and_3_of_10(self):
        stories=prepared_news(3)
        health=[{"feed_id":f["id"],"status":"ok","verified_links":1}
                for f in CFG["feeds"]]
        with tempfile.TemporaryDirectory() as folder:
            word,verified,held,degraded=prepare_source_limited_verified_word(
                stories,CFG,Path(folder),
                title="رصد | تقرير المتابعة الساعية — اختبار محلي فقط",
                start="٢١ نوفمبر، الساعة ١٨:٠٠ القاهرة",
                end="٢١ نوفمبر، الساعة ١٩:٠٠ القاهرة",
                source_records=health,report_kind="hourly",
                capture=synthetic_capture)
            self.assertEqual((len(verified),held,degraded),(3,0,True))
            self.assertEqual([x["id"] for x in verified],
                             [x["id"] for x in stories])
            doc=Document(word)
            self.assertEqual(len(doc.inline_shapes),3)
            text="\n".join(p.text for p in doc.paragraphs)
            self.assertIn("3 أخبار موثقة من أصل 10 مستهدفة",text)
            self.assertIn("النقص 7",text)
            self.assertIn("تحليل الرصد",text)
            self.assertIn("توزيع التغطيات على المواقع",text)
            cover=doc.tables[0].cell(0,0).text
            self.assertIn("تقرير المتابعة الساعية",cover)
            self.assertIn("التغطيات المصوّرة",cover)
            for story in stories:
                self.assertIn(story["headline"],text)
                self.assertTrue(any(
                    rel.target_ref==story["url"]
                    for rel in doc.part.rels.values()
                    if rel.reltype.endswith("/hyperlink")))
            digest=[{"status":"verified","sha256":hashlib.sha256(
                Path(row["evidence_image_path"]).read_bytes()).hexdigest()}
                for row in verified]
            self.assertTrue(word_images_match_capture_digests(word,digest))

    def test_one_photo_hold_keeps_two_real_images_not_fake_missing_third(self):
        stories=prepared_news(3)
        health=[{"feed_id":f["id"],"status":"ok","verified_links":1}
                for f in CFG["feeds"]]
        held=[]
        def capture(article,feeds,destination):
            if article["id"]==stories[1]["id"]:
                return {"status":"hold","reason":"publisher_access_refused"}
            return synthetic_capture(article,feeds,destination)
        with tempfile.TemporaryDirectory() as folder:
            doc,verified,rejected,degraded=prepare_source_limited_verified_word(
                stories,CFG,Path(folder),
                title="رصد | ساعة الرصد — بيانات اختبار فقط",
                start="21 نوفمبر، 18:00",end="21 نوفمبر، 19:00",
                source_records=health,report_kind="hourly",
                held_items=held,capture=capture)
            self.assertEqual((len(verified),rejected,degraded),(2,1,True))
            self.assertEqual(len(held),1)
            self.assertEqual(held[0]["reason"],"publisher_access_refused")
            word=Document(doc)
            self.assertEqual(len(word.inline_shapes),2)
            paragraphs="\n".join(p.text for p in word.paragraphs)
            self.assertIn("2 أخبار موثقة من أصل 10 مستهدفة",paragraphs)
            self.assertIn("النقص 8",paragraphs)
            self.assertTrue(word_images_match_capture_digests(doc,[
                {"status":"verified","sha256":hashlib.sha256(
                    Path(row["evidence_image_path"]).read_bytes()).hexdigest()}
                for row in verified
            ]))


if __name__=="__main__":
    unittest.main()
