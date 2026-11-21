"""Production report builder must share the approved daily navy/gold Word style.

No SMTP, publisher network, or private state. Publisher screenshots are
synthetic TEST-ONLY, never represented as real articles.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from monitor import article_id
from scheduled_rasd import prepare_source_limited_verified_word

URL="https://hapijournal.com/2026/11/21/test-publisher-visual-only"
SOURCE="Hapi native news RSS"

def synthetic_capture(article, feeds, dest):
    assert article["url"] == URL and feeds[0]["name"] == SOURCE
    pic=Image.new("RGB",(1200,900),"white")
    brush=ImageDraw.Draw(pic)
    brush.rectangle((0,0,1200,190),fill=(12,32,71))
    for i in range(13):
        brush.rectangle((44,230+45*i,1100-i*15,248+45*i),fill=(65,95,139))
    pic.save(dest,format="JPEG",quality=93)
    return {"status":"verified","sha256":hashlib.sha256(
        Path(dest).read_bytes()).hexdigest()}

class RealPeriodicWordTemplateParity(unittest.TestCase):
    def test_real_builder_uses_daily_template_and_exact_original_evidence(self):
        article={
            "id":article_id(URL),
            "headline":"وزارة التخطيط تتابع مشروعات التنمية في السويس",
            "publisher_excerpt":"هذا نص اختبار مصطنع لا يمثل خبرًا منشورًا",
            "source":SOURCE,"url":URL,
            "published_at_cairo":"2026-11-21 18:00 EET",
            "published_display_cairo":"21 نوفمبر 2026 الساعة 18:00",
        }
        config={"feeds":[{"id":"hapi","name":SOURCE,
                          "allowed_article_hosts":["hapijournal.com"]}]}
        health=[{"feed_id":"hapi","status":"ok","verified_links":1}]
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)
            word,items,held,limited=prepare_source_limited_verified_word(
                [article],config,output,
                title="رصد | تقرير المتابعة الدورية — اختبار شكل فقط",
                start="21 نوفمبر 2026 الساعة 17:30",
                end="21 نوفمبر 2026 الساعة 18:00",
                source_records=health,
                capture=synthetic_capture,
            )
            self.assertEqual((len(items),held,limited),(1,0,False))
            doc=Document(word)
            self.assertEqual(len(doc.inline_shapes),1)
            self.assertIn("تقرير المتابعة النصف ساعية",doc.tables[0].cell(0,0).text)
            self.assertIn("رصد",doc.tables[0].cell(0,0).text)
            self.assertEqual(doc.core_properties.author,"RASD")
            self.assertIn("تحليل الرصد","\n".join(p.text for p in doc.paragraphs))
            self.assertIn("توزيع التغطيات على المواقع",
                          "\n".join(p.text for p in doc.paragraphs))
            proof=[{"status":"verified","sha256":hashlib.sha256(
                Path(items[0]["evidence_image_path"]).read_bytes()).hexdigest()}]
            self.assertTrue(word_images_match_capture_digests(word,proof))

    def test_hourly_news_cannot_hide_unknown_time_bucket(self):
        # The renderer would otherwise accidentally report recovered old
        # news as fresh. Strict classification must fail before photo I/O.
        article={"id":article_id(URL),"url":URL}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"hourly_publication_bucket_missing"):
                prepare_source_limited_verified_word(
                    [article],{"feeds":[]},Path(d),
                    title="رصد ساعي",start="a",end="b",source_records=[],
                    report_kind="hourly",
                    capture=lambda *_: (_ for _ in ()).throw(
                        AssertionError("No picture should be captured")))

if __name__=="__main__":
    unittest.main()
