"""Original publisher screenshot recovery + 14th native local source, no network."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image,ImageDraw

from capture_public import (
    accept_staged_image,allowed_url,capture_verified_original_frame)
from monitor import APPROVED_FEED_URLS,parse_rss

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL="https://www.alnaharegypt.com/1205331"


class NativeNaharAndOriginalPhotoNoSend(unittest.TestCase):
    def test_fourteenth_publisher_approved_explicitly(self):
        config=json.loads((ROOT/"sources_newsroom_active.json").read_text("utf-8"))
        self.assertEqual(len(config["feeds"]),14)
        feed=next(x for x in config["feeds"] if x["id"]=="alnaharegypt")
        self.assertIn(feed["url"],APPROVED_FEED_URLS)
        self.assertTrue(allowed_url(ORIGINAL,"alnaharegypt.com"))
        self.assertTrue(allowed_url(
            "https://www.alnaharegypt.com/uploads/images/pic.jpg",
            "alnaharegypt.com",asset=True))
        self.assertFalse(allowed_url(
            "https://evil.alnaharegypt.com.bad.invalid/image.jpg",
            "alnaharegypt.com",asset=True))
        data=(
            "<rss version='2.0'><channel><item>"
            "<title>وزير التخطيط يناقش خطة التنمية</title>"
            f"<link>{ORIGINAL}</link>"
            "<description>وزارة التخطيط والتنمية الاقتصادية</description>"
            "<pubDate>Sat, 21 Nov 2026 16:00:00 +0000</pubDate>"
            "</item></channel></rss>").encode("utf-8")
        count,items=parse_rss(data,feed,config["keywords"],
                              now=datetime(2026,11,21,17,tzinfo=timezone.utc),
                              require_complete_items=True)
        self.assertEqual((count,len(items)),(1,1))
        self.assertEqual(items[0]["source"],feed["name"])

    def test_sparse_but_readable_real_jpeg_under_8kb_is_no_longer_discarded(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            image=Image.new("RGB",(800,500),"white")
            d=ImageDraw.Draw(image)
            d.rectangle((0,0,799,80),fill=(15,32,65))
            d.rectangle((30,120,740,145),fill=(33,48,74))
            staged,dest=base/"staged.jpg",base/"verified.jpg"
            image.save(staged,"JPEG",quality=20,optimize=True)
            self.assertGreaterEqual(staged.stat().st_size,3000)
            self.assertLess(staged.stat().st_size,8000)
            result=accept_staged_image(staged,dest)
            self.assertTrue(result["ok"])
            self.assertEqual(result["sha256"],hashlib.sha256(dest.read_bytes()).hexdigest())

    def test_nearly_blank_frame_under_3kb_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            staged,dest=base/"staged.jpg",base/"not-approved.jpg"
            Image.new("RGB",(600,400),"white").save(staged,"JPEG",quality=25,optimize=True)
            self.assertLess(staged.stat().st_size,3000)
            result=accept_staged_image(staged,dest)
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"],"screenshot_too_small")
            self.assertFalse(dest.exists())


class DummyHeadline:
    def bounding_box(self):
        return {"x":55,"y":120,"width":800,"height":55}


class DummyArticlePage:
    def __init__(self,*,always_skeleton=False,navigate=False):
        self.url=ORIGINAL
        self.viewport_size={"width":1200,"height":900}
        self.screenshots=0
        self.delays=0
        self.always_skeleton=always_skeleton
        self.navigate=navigate

    def screenshot(self,*,path,type,quality,full_page,timeout):
        self.screenshots+=1
        img=Image.new("RGB",(1200,900),"white")
        p=ImageDraw.Draw(img)
        p.rectangle((0,0,1199,160),fill=(18,40,68))
        p.rectangle((70,195,710,240),fill=(25,28,34))
        p.rectangle((810,160,1150,550),fill=(12,95,140))
        p.rectangle((45,355,780,745),fill=(247,247,247))
        if self.screenshots>1 and not self.always_skeleton:
            for x in range(50,770,45):
                p.rectangle((x,355,x+40,744),
                            fill=((50+x)%220,(20+x//2)%220,(130+x)%220))
        img.save(path,"JPEG",quality=quality)

    def wait_for_timeout(self,ms):
        self.delays+=1
        if self.navigate:
            self.url="https://www.alnaharegypt.com/another-news"


class PublisherFrameRecoveryNoSend(unittest.TestCase):
    def test_one_passive_wait_recaptures_same_real_page_and_proves_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"original.jpg"
            page=DummyArticlePage()
            with patch("capture_public.original_article_images_loaded",return_value=True):
                result=capture_verified_original_frame(
                    page,"alnaharegypt.com",target,requested_url=ORIGINAL,
                    headline=DummyHeadline())
            self.assertTrue(result["ok"])
            self.assertEqual(page.screenshots,2)
            self.assertEqual(page.delays,1)
            self.assertEqual(result["sha256"],hashlib.sha256(target.read_bytes()).hexdigest())

    def test_two_placeholders_are_hold_and_never_create_original_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"original.jpg"
            page=DummyArticlePage(always_skeleton=True)
            with patch("capture_public.original_article_images_loaded",return_value=True):
                result=capture_verified_original_frame(
                    page,"alnaharegypt.com",target,requested_url=ORIGINAL,
                    headline=DummyHeadline())
            self.assertFalse(result["ok"])
            self.assertIn(result["reason"],{
                "visual_qa_suspicious_flat_original_lead_media",
                "visual_qa_blank_or_low_content"})
            self.assertEqual(page.screenshots,2)
            self.assertFalse(target.exists())

    def test_original_article_navigation_invalidates_waiting_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"original.jpg"
            page=DummyArticlePage(navigate=True)
            with patch("capture_public.original_article_images_loaded",return_value=True):
                result=capture_verified_original_frame(
                    page,"alnaharegypt.com",target,requested_url=ORIGINAL,
                    headline=DummyHeadline())
            self.assertEqual(result["reason"],"redirect_outside_publisher")
            self.assertEqual(page.screenshots,1)
            self.assertFalse(target.exists())

    def test_image_load_failure_still_holds_after_one_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"original.jpg"
            page=DummyArticlePage()
            with patch("capture_public.original_article_images_loaded",return_value=False):
                result=capture_verified_original_frame(
                    page,"alnaharegypt.com",target,requested_url=ORIGINAL,
                    headline=DummyHeadline())
            self.assertEqual(result["reason"],"original_article_image_not_loaded")
            self.assertFalse(target.exists())


if __name__=="__main__":
    unittest.main()
