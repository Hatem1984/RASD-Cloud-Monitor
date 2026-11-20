"""Two independently gated first-party HTML origins through RASD's hourly Word."""
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from monitor import article_id
from cloud_proof_report import word_images_match_capture_digests
from rasd_original_html_source_gate import (
    all_newsroom_origins,collection_origins,YOUM7_SOURCE,ALMAL_SOURCE)
from scheduled_rasd import discover_interval_news,prepare_source_limited_verified_word


class Youm7GatedHourNoSend(unittest.TestCase):
    NOW=datetime(2026,11,20,18,7,tzinfo=timezone.utc)
    Y7_URL=("https://www.youm7.com/story/2026/11/20/"
            "planning-sustainable-projects/7625874")
    MAL_URL="https://almalnews.com/2148532/sustainable-planning/"

    def setUp(self):
        self.cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
        self.assertEqual(self.cfg["original_html_sources"],[
            ALMAL_SOURCE,YOUM7_SOURCE])

    def inspector(self,config,now,*,article_limit,require_complete_items):
        return {"sources":[{"feed_id":f["id"],"status":"ok","verified_links":2}
                           for f in config["feeds"]],
                "matched_public_articles":[],
                "matched_article_pool_truncated":False}

    def y7_result(self):
        return {"original_pages_dated":1,"original_page_hold":0,
                "old_dated_stories_excluded":2,
                "stories":[{
                    "id":article_id(self.Y7_URL),"url":self.Y7_URL,
                    "headline":"وزير التخطيط يعلن تفاصيل مشروعات التنمية",
                    "source":YOUM7_SOURCE["name"],
                    "published":"Fri, 20 Nov 2026 17:05:00 +0000",
                    "publisher_excerpt":"",
                }]}

    def mal_result(self):
        return {"original_page_verified":1,"original_page_hold":0,
                "stories":[{
                    "id":article_id(self.MAL_URL),"url":self.MAL_URL,
                    "headline":"وزير التخطيط يبحث تطوير بورسعيد",
                    "source":ALMAL_SOURCE["name"],
                    "published":"Fri, 20 Nov 2026 17:15:00 +0000",
                    "publisher_excerpt":"",
                }]}

    @staticmethod
    def capture(row,feeds,image):
        expected=next(x for x in feeds if x["name"]==row["source"])
        assert expected["id"] in ("almal_html","youm7_html")
        p=Image.new("RGB",(1200,900),"white")
        d=ImageDraw.Draw(p)
        d.rectangle((0,0,1199,160),fill=(11,38,79))
        for y in range(190,880,40):
            d.rectangle((45,y,1100,y+17),fill=(40,85,141))
        p.save(image,"JPEG",quality=90)
        return {"status":"verified","sha256":hashlib.sha256(
            Path(image).read_bytes()).hexdigest()}

    def test_youm7_source_off_by_default_and_no_legacy_rss_regression(self):
        with patch.dict(os.environ,{
            "RASD_YOUM7_ORIGINAL_HTML_ENABLED":"false",
            "RASD_ALMAL_ORIGINAL_HTML_ENABLED":"false"}),\
             patch("rasd_youm7_tag_original_research.research",
                   side_effect=AssertionError("no Youm7 IO when disabled")):
            rows=[]
            items=discover_interval_news(
                self.cfg,self.NOW,inspector=self.inspector,
                source_records=rows,published_before=self.NOW.replace(minute=0))
        self.assertEqual(items,[])
        self.assertEqual(len(rows),14)
        self.assertEqual(len(all_newsroom_origins(self.cfg)),16)
        self.assertEqual(len(collection_origins(self.cfg)),14)

    def test_youm7_page_and_image_enter_ministry_hourly_word_no_send(self):
        with patch.dict(os.environ,{
            "RASD_YOUM7_ORIGINAL_HTML_ENABLED":"true",
            "RASD_ALMAL_ORIGINAL_HTML_ENABLED":"false"}),\
             patch("rasd_youm7_tag_original_research.research",
                   return_value=self.y7_result()),\
             patch("rasd_almal_original_html_research.research",
                   side_effect=AssertionError("Al Mal still disabled")),\
             tempfile.TemporaryDirectory() as temp:
            health=[]
            news=discover_interval_news(
                self.cfg,self.NOW,inspector=self.inspector,
                source_records=health,published_before=self.NOW.replace(minute=0))
            self.assertEqual(len(news),1)
            self.assertEqual(news[0]["hourly_publication_bucket"],
                             "within_previous_hour")
            self.assertEqual(len(health),15)
            self.assertEqual(health[-1]["feed_id"],"youm7_html")
            self.assertEqual(health[-1]["status"],"ok")
            word,delivered,held,limited=prepare_source_limited_verified_word(
                news,self.cfg,Path(temp),title="رصد | ساعي تجريبي",
                start="السادسة",end="السابعة",report_kind="hourly",
                source_records=health,capture=self.capture)
            self.assertEqual((len(delivered),held,limited),(1,0,False))
            self.assertTrue(word_images_match_capture_digests(
                word,[{"status":"verified","sha256":hashlib.sha256(
                    Path(delivered[0]["evidence_image_path"]).read_bytes()).hexdigest()}]))

    def test_both_optional_publishers_enforce_separate_source_health(self):
        with patch.dict(os.environ,{
            "RASD_YOUM7_ORIGINAL_HTML_ENABLED":"true",
            "RASD_ALMAL_ORIGINAL_HTML_ENABLED":"true"}),\
             patch("rasd_youm7_tag_original_research.research",
                   return_value=self.y7_result()),\
             patch("rasd_almal_original_html_research.research",
                   return_value=self.mal_result()):
            health=[]
            articles=discover_interval_news(
                self.cfg,self.NOW,inspector=self.inspector,
                source_records=health,published_before=self.NOW.replace(minute=0))
        self.assertEqual(len(articles),2)
        self.assertEqual(len({a["id"] for a in articles}),2)
        self.assertEqual([h["feed_id"] for h in health][-2:],
                         ["almal_html","youm7_html"])
        self.assertEqual(len(health),16)

    def test_spoofed_youm7_host_never_qualifies_even_degraded(self):
        bad=self.y7_result()
        bad["stories"][0]["url"]="https://www.youm7.com.evil.example/notice"
        bad["stories"][0]["id"]=article_id(bad["stories"][0]["url"])
        with patch.dict(os.environ,{
            "RASD_YOUM7_ORIGINAL_HTML_ENABLED":"true",
            "RASD_ALMAL_ORIGINAL_HTML_ENABLED":"false"}),\
             patch("rasd_youm7_tag_original_research.research",return_value=bad):
            with self.assertRaisesRegex(ValueError,"unapproved_news_publisher"):
                discover_interval_news(
                    self.cfg,self.NOW,inspector=self.inspector,
                    published_before=self.NOW.replace(minute=0),
                    allow_degraded=True)


if __name__=="__main__":
    unittest.main()
