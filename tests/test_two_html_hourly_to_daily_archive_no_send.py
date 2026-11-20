"""Lossless nightly archive of TWO distinct first-party HTML hourly sources.

Gmail and sender are synthetic; all images are synthetic. This is proof of
source identity preservation from 2 hourly photos to the 22:00 rollup, never
proof that real production mail was sent or received.
"""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

from monitor import article_id
from daily_report import render_docx
from daily_sent_consolidator import consolidate_sent_words
from scheduled_rasd import news_for_rollup
from cloud_proof_report import word_images_match_capture_digests
from test_daily_sent_consolidation import (
    FakeSent, MergeActualDeliveredWord, SENDER, RECIPIENT)

ROOT=Path(__file__).resolve().parents[1]


class TwoGatedHtmlOriginalsDailyArchiveNoSend(unittest.TestCase):
    def make_image(self,path,index):
        pic=Image.new("RGB",(1200,900),"white")
        art=ImageDraw.Draw(pic)
        art.rectangle((0,0,1199,180),fill=(14,35,70))
        for y in range(220,880,38):
            art.rectangle((60,y,1160-index*100,y+16),
                          fill=(47+index*15,90,138))
        pic.save(path,format="JPEG",quality=89)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_source_specific_hourly_cards_into_daily_original_jpeg_archive(self):
        config=json.loads((ROOT/"sources_newsroom_active.json").read_text("utf-8"))
        with tempfile.TemporaryDirectory(prefix="rasd-two-html-hourly-daily-") as td:
            root=Path(td)
            urls=[
                "https://almalnews.com/2148532/egypt-planning/",
                "https://www.youm7.com/story/2026/11/20/"
                "egypt-planning-ministry/7625874",
            ]
            sources=["Al Mal native publisher HTML",
                     "Youm7 first-party Ministry tag HTML"]
            originals=[]
            evidence=[]
            for n,(url,source) in enumerate(zip(urls,sources)):
                record={
                    "id":article_id(url), "headline":(
                        "وزير التخطيط يتابع التنمية الاقتصادية في مصر "+str(n)),
                    "publisher_excerpt":"خلاصات تجريبية فقط",
                    "source":source, "url":url,
                    "published_at_cairo":"2026-11-20 17:05 EET",
                    "published_display_cairo":"20 نوفمبر 2026",
                }
                photo=root/("publisher-"+str(n)+".jpg")
                sha=self.make_image(photo,n)
                originals.append(record)
                evidence.append((photo,sha))
            hourly={
                "report_period":"interval",
                "report_kind":"hourly",
                "ministry_media_grid":True,
                "coverage":"HEALTHY",
                "title":"رصد | تقرير المتابعة الساعية — عينة لا ترسل",
                "display_window_start":"20 نوفمبر 2026 الساعة 17:00",
                "display_window_end":"20 نوفمبر 2026 الساعة 18:00",
                "hourly_in_period":2,"hourly_recovered":0,
                "verified_links":2,
                "articles":[{**x,"evidence_image_path":str(evidence[i][0]),
                             "hourly_publication_bucket":"within_previous_hour"}
                            for i,x in enumerate(originals)],
                "sources":[{"feed_id":"almal_html","status":"ok",
                            "verified_links":1},
                           {"feed_id":"youm7_html","status":"ok",
                            "verified_links":1}],
            }
            hourly_word=root/"RASD-News-With-Original-Screenshots.docx"
            render_docx(hourly,hourly_word)
            self.assertTrue(word_images_match_capture_digests(
                hourly_word,[{"status":"verified","sha256":sha}
                             for _,sha in evidence]))
            key="<rasd-"+("a"*24)+"@gmail.com>"
            synthetic_email=MergeActualDeliveredWord().mail(
                key,hourly_word.read_bytes())
            fake_sent=FakeSent({key:synthetic_email})
            state={"entries":{
                row["id"]:{
                    "status":"smtp_accepted","kind":"interval_item",
                    "news":row,"message_id":key,
                    "accepted_at":"2026-11-20T19:00:00+02:00"}
                for row in originals}}
            eligible=news_for_rollup(state,"2026-11-20",config)
            self.assertEqual(len(eligible),2)
            # Production rollup sorts by publisher date then article ID,
            # not by the ordering of cards in the hourly message.
            self.assertEqual({x["id"] for x in eligible},
                             {x["id"] for x in originals})
            archive,proof=consolidate_sent_words(
                eligible,state,root/"daily",
                sender=SENDER,recipient=RECIPIENT,
                app_password="offline-only",
                start="19 نوفمبر 22:00 القاهرة",
                end="20 نوفمبر 22:00 القاهرة",
                title="رصد | التقرير المجمع اليومي — عينة",
                config=config,client_factory=lambda:fake_sent)
            final=Document(archive)
            self.assertEqual(len(final.inline_shapes),2)
            self.assertTrue(word_images_match_capture_digests(archive,proof))
            original_sha_by_id={
                originals[i]["id"]:evidence[i][1]
                for i in range(len(originals))
            }
            self.assertEqual([x["sha256"] for x in proof],
                             [original_sha_by_id[x["id"]] for x in eligible])
            self.assertTrue(fake_sent.selected_readonly)
            self.assertEqual(fake_sent.searched,[key])
            self.assertEqual(fake_sent.logout_count,1)


if __name__=="__main__":
    unittest.main()
