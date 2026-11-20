"""No-network regression for original Al Mal article -> JPEG -> Word only."""
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from monitor import article_id
from rasd_almal_end_to_end_shadow_no_send import build_shadow


class AlmalEndToEndShadowNoSend(unittest.TestCase):
    when=datetime(2026,11,20,18,30,tzinfo=timezone.utc)
    original="https://almalnews.com/2148532/news-planning-example/"

    def original_result(self):
        return {"stories":[{
            "id":article_id(self.original),
            "source":"Al Mal native publisher HTML",
            "headline":"وزير التخطيط يبحث التنمية المستدامة",
            "url":self.original, "published":"Fri, 20 Nov 2026 17:05:00 +0000",
            "publisher_excerpt":"خبر تجريبي فقط",
        }]}

    @staticmethod
    def synthetic_original(row, feeds, path):
        if feeds[0]["name"]!="Al Mal native publisher HTML":
            raise AssertionError("wrong publisher")
        img=Image.new("RGB",(1200,900),"white")
        ink=ImageDraw.Draw(img)
        ink.rectangle((0,0,1199,175),fill=(11,32,73))
        for y in range(210,880,40):
            ink.rectangle((60,y,1120,y+17),fill=(46,93,145))
        ink.text((90,50),row["headline"],fill=(220,220,220))
        img.save(path,"JPEG",quality=88)
        return {"status":"verified","sha256":hashlib.sha256(
            Path(path).read_bytes()).hexdigest()}

    def test_one_own_page_image_makes_exact_ministry_word_without_email(self):
        result=build_shadow(
            self.when, discover=lambda now:self.original_result(),
            capture=self.synthetic_original)
        self.assertEqual(result["original_html_matches_72h"],1)
        self.assertEqual(result["original_page_images_verified"],1)
        self.assertEqual(result["new_previous_complete_hour"],1)
        self.assertEqual(result["recovered_previous_hours"],0)
        self.assertTrue(result["ministry_word_verified"])
        self.assertGreater(result["ministry_word_bytes"],3000)
        self.assertFalse(result["smtp_sent"])
        self.assertFalse(result["production_activated"])

    def test_original_photo_refusal_does_not_make_word_or_send(self):
        result=build_shadow(
            self.when,discover=lambda now:self.original_result(),
            capture=lambda row,feeds,path:{
                "status":"hold","reason":"publisher_access_refused"})
        self.assertEqual(result["original_page_images_held"],1)
        self.assertEqual(result["original_page_images_verified"],0)
        self.assertFalse(result["ministry_word_verified"])
        self.assertFalse(result["smtp_sent"])

    def test_unapproved_article_origin_refused_before_capture(self):
        corrupted=self.original_result()
        corrupted["stories"][0]["url"]="https://malicious.example/notice"
        with self.assertRaisesRegex(RuntimeError,"almal_shadow_original_url_hold"):
            build_shadow(self.when,discover=lambda now:corrupted,
                         capture=lambda *a,**kw:self.fail("capture must not run"))

    def test_recovered_old_content_not_claimed_as_hourly_news(self):
        example=self.original_result()
        example["stories"][0]["published"]="Thu, 19 Nov 2026 17:05:00 +0000"
        result=build_shadow(
            self.when, discover=lambda now:example,
            capture=self.synthetic_original)
        self.assertTrue(result["ministry_word_verified"])
        self.assertEqual(result["new_previous_complete_hour"],0)
        self.assertEqual(result["recovered_previous_hours"],1)


if __name__=="__main__":
    unittest.main()
