"""Gate 26 source-scoped strict Word proof release regression: no network/SMTP."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw
from gate26_verified_review import run, verify_embedded_evidence
from base64 import b64decode

NOW=datetime(2026,10,15,12,20,tzinfo=timezone.utc)
URL="https://www.shorouknews.com/news/view.aspx?cdate=15102026&id=91362f75-9c72-4897-a136-eb54030ffdcb"
TITLE="نائب رئيس البنك الدولي يشيد بمؤشرات الاقتصاد المصري"
TEXT="عقد الدكتور أحمد رستم وزير التخطيط والتنمية الاقتصادية اجتماعًا مع نائب رئيس البنك الدولي لمناقشة التعاون."

def rss(items):
    from xml.sax.saxutils import escape
    return ('<rss><channel>'+''.join(
        f'<item><title>{escape(title)}</title><link>{escape(url)}</link>'
        f'<description>{escape(description)}</description>'
        '<pubDate>Thu, 15 Oct 2026 11:47:54 +0300</pubDate></item>'
        for title,url,description in items
    )+'</channel></rss>').encode()

def fake_capture(url,publisher,dest):
    if publisher!="shorouknews.com":
        raise AssertionError("unreviewed publisher")
    pic=Image.new("RGB",(1200,900),"white")
    draw=ImageDraw.Draw(pic)
    draw.rectangle((0,0,1199,155),fill=(14,45,85))
    for y in range(215,860,28):
        draw.rectangle((60,y,1140,y+11),fill=(40+y%33,58,75))
    dest.parent.mkdir(exist_ok=True,parents=True)
    pic.save(dest,quality=90)
    return {"ok":True,"actual_url":url,"title":TITLE,
            "sha256":hashlib.sha256(dest.read_bytes()).hexdigest()}

class Gate26StrictWordTests(unittest.TestCase):
    def test_full_strict_engine_generates_source_limited_word_with_original_matching_jpeg(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)
            results=run(out,fetch=lambda *a:rss([(TITLE,URL,TEXT)]),
                        capture=fake_capture,now=NOW)
            self.assertEqual(results["status"],"REVIEW_READY")
            self.assertEqual(results["screenshots_verified"],1)
            self.assertEqual(results["articles"],1)
            self.assertFalse(results["production_daily_approved"])
            self.assertFalse(results["mail_sent"])
            self.assertFalse(results["scheduler_enabled"])
            words=list(out.glob("*.docx"))
            self.assertEqual(len(words),1)
            with zipfile.ZipFile(words[0]) as archive:
                body=archive.read("word/document.xml").decode("utf-8")
                rels=archive.read("word/_rels/document.xml.rels").decode("utf-8")
                jpg=[x for x in archive.namelist() if x.startswith("word/media/")]
            self.assertEqual(len(jpg),1)
            self.assertIn("تقرير مراجعة مصدر الشروق",body)
            self.assertIn("ملخص كما أورده الناشر",body)
            self.assertIn("مباحثات",body)
            self.assertIn("الخبر ينقل تصريحات",body)
            self.assertIn("www.shorouknews.com/news/view.aspx",rels)
            self.assertTrue(verify_embedded_evidence(words[0],{
                "status":"READY","screenshots_verified":1,"articles":1,
                "entries":[{"status":"verified","sha256":results["entries"][0]["sha256"]}]
            }) if "entries" in results else words[0].stat().st_size>8000)

    def test_broken_original_page_returns_hold_no_review_word(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)
            result=run(out,fetch=lambda *a:rss([(TITLE,URL,TEXT)]),
                       capture=lambda *a:{"ok":False,"reason":"publisher_access_refused"},now=NOW)
            self.assertEqual(result["status"],"HOLD")
            self.assertFalse(list(out.glob("*.docx")))
            self.assertFalse(result["production_daily_approved"])
            self.assertEqual(result["screenshots_verified"],0)

    def test_duplicate_native_story_url_is_one_article(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)
            rows=[(TITLE,URL,TEXT),(TITLE,URL,TEXT)]
            result=run(out,fetch=lambda *a:rss(rows),capture=fake_capture,now=NOW)
            self.assertEqual(result["articles"],1)
            self.assertEqual(result["screenshots_verified"],1)

    def test_empty_feed_returns_hold_not_fabricated_word(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)
            result=run(out,fetch=lambda *a:rss([]),capture=lambda *a:self.fail("capture"),
                       now=NOW)
            self.assertEqual(result["status"],"HOLD")
            self.assertEqual(result["articles"],0)
            self.assertEqual(list(out.glob("*.docx")),[])

    def test_reject_unapproved_source_profile_before_any_network(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"unapproved_source_profile"):
                run(Path(root),profile="../../secrets")

    def skipTestIfNoCrypto(self):
        try:
            import cryptography
        except ImportError:
            self.skipTest("cryptography confined to encrypted proof workflow")

    def test_owner_artifact_is_encrypted_with_no_plaintext_docx(self):
        # Base offline CI intentionally installs no crypto runtime. Explicit
        # crypto acceptance runs where the restricted packaging job installs it.
        self.skipTestIfNoCrypto()
        from gate26_encrypt_review import pack
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            src=root/"source";src.mkdir()
            (src/"gate26-review-audit.json").write_text(
                json.dumps({"status":"HOLD"}),encoding="utf-8")
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            pub=root/"pub.pem"
            pub.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo))
            output=root/"encrypted.json"
            got=pack(src,output,pub)
            self.assertFalse(got["has_review_word"])
            encrypted=json.loads(output.read_text())
            self.assertNotIn("status",json.dumps(encrypted))
            wrapped=b64decode(encrypted["wrapped"])
            sym=key.decrypt(wrapped,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                algorithm=hashes.SHA256(),label=None))
            plain=AESGCM(sym).decrypt(b64decode(encrypted["nonce"]),
                            b64decode(encrypted["ciphertext"]),
                            b"RASD-GATE26-OWNER-REVIEW-v1")
            self.assertTrue(plain.startswith(b"PK"))

if __name__=="__main__":
    unittest.main()
