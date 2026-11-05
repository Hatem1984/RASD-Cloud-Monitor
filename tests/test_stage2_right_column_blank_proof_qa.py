"""Offline conservative right-column blank original-page proof regression.

All pictures in this test are SYNTHETIC test fixtures; never news evidence.
"""
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from capture_public import image_quality

def publisher_like_image(path, blank_right):
    img=Image.new("RGB",(1200,900),(235,239,242))
    d=ImageDraw.Draw(img)
    d.rectangle((0,0,1200,55),fill=(18,40,65))
    d.rectangle((175,340,484,375),fill=(93,130,149))
    for y in range(395,760,33):
        d.rectangle((211,y,445,y+8),fill=(40,55,70))
    d.rectangle((560,125,1120,137),fill=(25,36,45))
    d.rectangle((610,167,1080,179),fill=(25,36,45))
    for y in range(710,870,36):
        d.rectangle((550,y,1100,y+8),fill=(42,46,49))
    if not blank_right:
        for x in range(552,1115,38):
            d.rectangle((x,300,x+35,550),
                        fill=((x*3)%210,(x*7)%185+35,(x*13)%155+45))
    img.save(path,format="JPEG",quality=92)

class RightColumnPublisherProof(unittest.TestCase):
    def test_right_side_blank_hero_and_readable_headline_still_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            photo=Path(temp)/"blocked-original.jpg"
            publisher_like_image(photo,True)
            result=image_quality(photo)
            self.assertEqual(result["reason"],"suspicious_flat_original_lead_media")
            self.assertFalse(result["accepted"])
    def test_right_side_detailed_article_image_keeps_frame_eligible(self):
        with tempfile.TemporaryDirectory() as temp:
            photo=Path(temp)/"legible-original.jpg"
            publisher_like_image(photo,False)
            result=image_quality(photo)
            self.assertEqual(result["reason"],"ok")
            self.assertTrue(result["accepted"])
if __name__=="__main__":unittest.main()
