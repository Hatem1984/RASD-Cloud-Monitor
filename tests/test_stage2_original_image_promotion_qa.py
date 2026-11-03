"""Offline screenshot evidence staging regression. Synthetic pixels are QA fixtures, NOT publisher evidence."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from cloud_proof_report import proof_capture
from monitor import article_id

URL="https://hapijournal.com/qa-original-article"
ARTICLE={"id":article_id(URL),"url":URL,
         "headline":"وزارة التخطيط تعلن نتائج جديدة للمشروعات",
         "source":"Hapi native news RSS"}
FEEDS=[{"name":"Hapi native news RSS",
        "allowed_article_hosts":["hapijournal.com","www.hapijournal.com"]}]

def make_fixture(path:Path)->str:
    """Deliberate synthetic checkerboard. Never use as a real-page proof."""
    img=Image.new("RGB",(1200,900),"white")
    d=ImageDraw.Draw(img)
    for x in range(0,1200,19):
        for y in range(0,900,19):
            val=(x*7+y*11)//19
            d.rectangle((x,y,x+17,y+17),fill=((val*31)%256,(val*17)%256,(val*43)%256))
    img.save(path,"JPEG",quality=88)
    return hashlib.sha256(path.read_bytes()).hexdigest()

class OriginalImageStaging(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.dest=self.root/"verified.jpg"
    def test_title_mismatch_staged_image_does_not_replace_older_verified(self):
        old=make_fixture(self.dest)
        original=self.dest.read_bytes()
        def mock(url,publisher,path):
            return {"ok":True,"actual_url":url,
                    "title":"خبر آخر لا يخص المصدر الأصلي",
                    "sha256":make_fixture(path)}
        result=proof_capture(ARTICLE,FEEDS,self.dest,capture=mock)
        self.assertEqual(result["status"],"hold")
        self.assertEqual(result["reason"],"title_mismatch")
        self.assertEqual(self.dest.read_bytes(),original)
        self.assertEqual(hashlib.sha256(self.dest.read_bytes()).hexdigest(),old)
        self.assertFalse(list(self.root.glob(".rasd-proof-*")))
    def test_wrong_url_staged_image_never_promoted(self):
        def mock(url,publisher,path):
            return {"ok":True,"actual_url":"https://hapijournal.com/other-article",
                    "title":ARTICLE["headline"],"sha256":make_fixture(path)}
        result=proof_capture(ARTICLE,FEEDS,self.dest,capture=mock)
        self.assertEqual(result["reason"],"url_mismatch")
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.root.glob(".rasd-proof-*")))
    def test_verified_promoted_and_digest_compared(self):
        staged=[]
        def mock(url,publisher,path):
            digest=make_fixture(path)
            staged.append(path)
            return {"ok":True,"actual_url":url,"title":ARTICLE["headline"],"sha256":digest}
        result=proof_capture(ARTICLE,FEEDS,self.dest,capture=mock)
        self.assertEqual(result["status"],"verified")
        self.assertTrue(self.dest.is_file())
        self.assertEqual(result["sha256"],hashlib.sha256(self.dest.read_bytes()).hexdigest())
        self.assertNotEqual(staged[0],self.dest)
        self.assertFalse(staged[0].exists())
        self.assertGreater(result["bytes"],8000)
    def test_failed_sha_does_not_overwrite_existing_proof(self):
        _=make_fixture(self.dest)
        original=self.dest.read_bytes()
        def mock(url,publisher,path):
            make_fixture(path)
            return {"ok":True,"actual_url":url,"title":ARTICLE["headline"],
                    "sha256":"0"*64}
        result=proof_capture(ARTICLE,FEEDS,self.dest,capture=mock)
        self.assertEqual(result["reason"],"screenshot_digest_mismatch")
        self.assertEqual(self.dest.read_bytes(),original)
    def test_failed_capture_does_not_create_evidence(self):
        result=proof_capture(ARTICLE,FEEDS,self.dest,
            capture=lambda *args:{"ok":False,"reason":"publisher_access_refused"})
        self.assertEqual(result["status"],"hold")
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.root.glob(".rasd-proof-*")))

if __name__=="__main__":unittest.main()
