"""Al Mal original HTML gated integration: no SMTP, network or private CAS."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from monitor import article_id
from rasd_original_html_source_gate import (
    ALMAL_SOURCE, all_newsroom_origins, collection_origins)
import scheduled_rasd as worker

ROOT=Path(__file__).resolve().parents[1]


class GatedOriginalHtmlNewsroom(unittest.TestCase):
    NOW=datetime(2026,11,20,18,7,tzinfo=timezone.utc)
    URL="https://almalnews.com/2148532/egypt-planning-news/"

    def setUp(self):
        self.config=json.loads(
            (ROOT/"sources_newsroom_active.json").read_text("utf-8"))
        self.assertEqual(len(self.config["feeds"]),14)
        self.assertEqual(self.config["original_html_sources"],[ALMAL_SOURCE])
        self.feed_source_rows=[]

    def inspector(self, config, now, *, article_limit, require_complete_items):
        self.assertEqual(article_limit,200)
        self.assertTrue(require_complete_items)
        return {
            "matched_public_articles":[],
            "matched_article_pool_truncated":False,
            "sources":[{"feed_id":x["id"],"status":"ok","verified_links":10}
                       for x in config["feeds"]],
        }

    def original_html(self):
        return {
            "original_page_verified":1,
            "original_page_hold":0,
            "stories":[{
                "id":article_id(self.URL),
                "source":"Al Mal native publisher HTML",
                "headline":"وزير التخطيط يبحث مشروعات التنمية",
                "url":self.URL,
                "published":"Fri, 20 Nov 2026 17:15:00 +0000",
                "publisher_excerpt":"",
            }]
        }

    def test_source_dormant_unless_owner_enables_explicit_gate(self):
        with patch.dict(os.environ,{"RASD_ALMAL_ORIGINAL_HTML_ENABLED":"false"}), \
             patch("rasd_almal_original_html_research.research",
                   side_effect=AssertionError("HTML network must not be queried")):
            observed=[]
            rows=worker.discover_interval_news(
                self.config,self.NOW,inspector=self.inspector,
                source_records=observed,published_before=self.NOW.replace(minute=0))
        self.assertEqual(rows,[])
        self.assertEqual(len(observed),14)
        self.assertEqual(len(collection_origins(self.config)),14)
        self.assertEqual(len(all_newsroom_origins(self.config)),15)

    @staticmethod
    def original_photo(article, sources, output):
        feed=next(x for x in sources if x["name"]==article["source"])
        assert feed["id"]=="almal_html"
        pic=Image.new("RGB",(1200,900),"white")
        art=ImageDraw.Draw(pic)
        art.rectangle((0,0,1199,165),fill=(10,32,70))
        for y in range(210,880,36):
            art.rectangle((50,y,1100,y+14),fill=(30,70,122))
        pic.save(output,"JPEG",quality=88)
        return {"status":"verified","sha256":hashlib.sha256(
            Path(output).read_bytes()).hexdigest()}

    def test_enabled_fifteenth_original_source_produces_hourly_ministry_word(self):
        with patch.dict(os.environ,{"RASD_ALMAL_ORIGINAL_HTML_ENABLED":"true"}), \
             patch("rasd_almal_original_html_research.research",
                   return_value=self.original_html()) as native, \
             tempfile.TemporaryDirectory() as td:
            source_records=[]
            items=worker.discover_interval_news(
                self.config,self.NOW,inspector=self.inspector,
                source_records=source_records,
                published_before=self.NOW.replace(minute=0))
            self.assertEqual(len(items),1)
            self.assertEqual(items[0]["hourly_publication_bucket"],
                             "within_previous_hour")
            self.assertEqual(len(source_records),15)
            self.assertEqual(source_records[-1]["feed_id"],"almal_html")
            native.assert_called_once()
            word,delivered,held,degraded=worker.prepare_source_limited_verified_word(
                items,self.config,Path(td),title="رصد | التقرير الساعي — اختبار",
                start="20 نوفمبر 2026 19:00",end="20 نوفمبر 2026 20:00",
                report_kind="hourly",source_records=source_records,
                capture=self.original_photo)
            self.assertEqual((len(delivered),held,degraded),(1,0,False))
            self.assertTrue(word.exists())
            self.assertTrue(word_images_match_capture_digests(
                word,[{"status":"verified","sha256":hashlib.sha256(
                    Path(delivered[0]["evidence_image_path"]).read_bytes()).hexdigest()}]))

    def test_malicious_discovery_cannot_be_silently_downgraded(self):
        hostile=self.original_html()
        hostile["stories"][0]["url"]="https://notalmal.example/2148532/spoof"
        hostile["stories"][0]["id"]=article_id(hostile["stories"][0]["url"])
        with patch.dict(os.environ,{"RASD_ALMAL_ORIGINAL_HTML_ENABLED":"true"}), \
             patch("rasd_almal_original_html_research.research",return_value=hostile):
            with self.assertRaisesRegex(ValueError,"unapproved_news_publisher"):
                worker.discover_interval_news(
                    self.config,self.NOW,inspector=self.inspector,
                    allow_degraded=True,published_before=self.NOW.replace(minute=0))

    def test_publisher_error_records_failed_source_without_fake_news(self):
        with patch.dict(os.environ,{"RASD_ALMAL_ORIGINAL_HTML_ENABLED":"true"}), \
             patch("rasd_almal_original_html_research.research",
                   side_effect=OSError("publisher offline")):
            records=[]
            result=worker.discover_interval_news(
                self.config,self.NOW,inspector=self.inspector,
                source_records=records,allow_degraded=True,
                published_before=self.NOW.replace(minute=0))
            self.assertEqual(result,[])
            self.assertEqual(records[-1]["status"],"failed")
            self.assertEqual(records[-1]["failure_code"],"other")
            self.assertEqual(len(records),15)

    def test_unreviewed_html_source_config_fails_before_network(self):
        tampered=json.loads(json.dumps(self.config))
        tampered["original_html_sources"][0]["homepage_url"]="https://evil.invalid/"
        with self.assertRaisesRegex(ValueError,"unreviewed_html_publisher_origin"):
            all_newsroom_origins(tampered)


if __name__=="__main__":
    unittest.main()
