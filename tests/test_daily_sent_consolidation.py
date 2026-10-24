"""Never recapture daily articles: merge actual SENT Word JPEG originals, offline."""
import hashlib
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from daily_sent_consolidator import (
    consolidate_sent_words, original_sent_word, sent_mailbox,
)


SENDER = "rasd.sender@gmail.com"
RECIPIENT = "owner.approved@gmail.com"


class FakeSent:
    def __init__(self, messages):
        self.messages = messages
        self.selected_readonly = None
        self.searched = []
        self.logout_count = 0

    def login(self, sender, password):
        if (sender, password) != (SENDER, "offline-only"):
            raise AssertionError("credentials_incorrect")
        return "OK", [b"ready"]

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, folder, readonly=False):
        self.selected_readonly = readonly
        return "OK", [b"2"]

    def uid(self, action, *args):
        if action == "SEARCH":
            key = args[-1].strip('"')
            self.searched.append(key)
            matches = [str(i+1).encode() for i, mid in enumerate(self.messages)
                       if mid == key]
            return "OK", [b" ".join(matches)]
        if action == "FETCH":
            index = int(args[0]) - 1
            raw = list(self.messages.values())[index]
            return "OK", [(b"1 (RFC822)", raw), b")"]
        raise AssertionError("only read-only search and fetch allowed")

    def logout(self):
        self.logout_count += 1
        return "BYE", []


class MergeActualDeliveredWord(unittest.TestCase):
    def source_news(self, index):
        return {
            "id": ("a" if index == 1 else "b")*24,
            "headline": "التخطيط: برنامج اقتصادي موثق " + str(index),
            "source": "Alborsa native Egyptian Economy RSS",
            "url": "https://www.alborsaanews.com/2026/10/23/20013" +
                   ("60" if index == 1 else "34"),
            "published_at_cairo": "2026-10-23 14:54 EEST",
            "published_display_cairo": "23 أكتوبر 2026",
            "publisher_excerpt": "منشور من الناشر الأصلي رقم " + str(index),
        }

    def sample_doc(self, output, group):
        out = Path(output)
        articles = []
        hashes = {}
        for story in group:
            picture = out / (story["id"] + ".jpg")
            im = Image.new("RGB", (1200, 900), "#f9f9f9")
            draw = ImageDraw.Draw(im)
            draw.rectangle((0, 0, 1199, 190), fill="#224466")
            # Images must be distinct: real publisher evidence is not
            # interchangeable across two different article identities.
            draw.rectangle((50, 35, 250+int(story["id"][0] == "b")*320, 90),
                           fill="#d1e8fa")
            for y in range(240, 860, 23):
                draw.rectangle((40, y, 1160, y+13), fill="#183146")
            im.save(picture, "JPEG", quality=88)
            hashes[story["id"]] = hashlib.sha256(picture.read_bytes()).hexdigest()
            articles.append({**story, "evidence_image_path": str(picture)})
        report = {
            "title": "رصد | نصف ساعة مصدر أصلي تجريبي",
            "display_window_start": "2026-10-23 14:00 Cairo",
            "display_window_end": "2026-10-23 14:30 Cairo",
            "coverage": "HEALTHY", "verified_links": len(articles),
            "articles": articles, "sources": [],
            "limitations": "صور أصلية موثقة في اختبار محلي فقط",
        }
        doc = out / ("interval-" + group[0]["id"] + ".docx")
        render_docx(report, doc)
        return doc.read_bytes(), hashes

    def mail(self, message_id, payload, from_address=SENDER):
        message = EmailMessage()
        message["From"] = from_address
        message["To"] = RECIPIENT
        message["Message-ID"] = message_id
        message["X-RASD-Delivery-ID"] = message_id[6:30]
        message["Subject"] = "RASD original interval"
        message.set_content("Verified original article JPG images inside Word")
        message.add_attachment(
            payload, maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="RASD-News-With-Original-Screenshots.docx",
        )
        return message.as_bytes()

    def test_two_sent_emails_make_one_daily_word_with_exact_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            stories = [self.source_news(1), self.source_news(2)]
            messages = {}
            state = {"entries": {}}
            expected_hashes = {}
            for index, news in enumerate(stories):
                original, hashes = self.sample_doc(directory, [news])
                expected_hashes.update(hashes)
                key = ("c" if index == 0 else "d")*24
                mid = "<rasd-" + key + "@gmail.com>"
                messages[mid] = self.mail(mid, original)
                state["entries"][news["id"]] = {
                    "status": "smtp_accepted",
                    "kind": "interval_item",
                    "news": news,
                    "message_id": mid,
                }
            imap = FakeSent(messages)
            config = {"feeds": [{"name":"Alborsa native Egyptian Economy RSS",
                         "id":"alborsa",
                         "allowed_article_hosts":["www.alborsaanews.com"]}]}
            word, proofs = consolidate_sent_words(
                stories, state, Path(directory) / "combined",
                sender=SENDER, recipient=RECIPIENT,
                app_password="offline-only",
                title="رصد | التقرير المجمع الحقيقي",
                start="22:00 أمس", end="22:00 اليوم", config=config,
                client_factory=lambda: imap,
            )
            actual=Document(word)
            self.assertEqual(len(actual.inline_shapes),2)
            self.assertIn("التقرير المجمع الحقيقي",
                          "\n".join(p.text for p in actual.paragraphs))
            self.assertEqual(
                {p["sha256"] for p in proofs},
                set(expected_hashes.values()))
            self.assertTrue(word_images_match_capture_digests(word,proofs))
            self.assertEqual(len(imap.searched),2)
            self.assertTrue(imap.selected_readonly)
            self.assertEqual(imap.logout_count,1)

    def test_invalid_sender_is_a_hard_hold_before_daily_send(self):
        with tempfile.TemporaryDirectory() as directory:
            news=self.source_news(1)
            original,_=self.sample_doc(directory,[news])
            mid="<rasd-"+("e"*24)+"@gmail.com>"
            imap=FakeSent({mid:self.mail(mid,original,"impostor@gmail.com")})
            imap.login(SENDER,"offline-only")
            sent_mailbox(imap)
            with self.assertRaisesRegex(
                RuntimeError,"daily_sent_message_headers_hold"):
                original_sent_word(imap,mid,SENDER,RECIPIENT)

    def test_unavailable_archive_fails_before_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            news=self.source_news(1)
            state={"entries":{news["id"]:{
                "status":"smtp_accepted", "kind":"interval_item",
                "news":news,
                "message_id":"<rasd-"+("e"*24)+"@gmail.com>",
            }}}
            with self.assertRaisesRegex(
                RuntimeError,"daily_sent_message_not_found"):
                consolidate_sent_words(
                    [news],state,Path(directory)/"out",sender=SENDER,
                    recipient=RECIPIENT,app_password="offline-only",
                    title="daily", start="yesterday",end="today",
                    config={"feeds":[]},
                    client_factory=lambda:FakeSent({}))


if __name__ == "__main__":
    unittest.main()
