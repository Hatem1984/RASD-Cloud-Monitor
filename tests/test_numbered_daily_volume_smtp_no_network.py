"""Owner-approved numbered daily production path: no SMTP or private network.

The fake ledger uses the production validation and receipt schema. Exercise
the actual 2+ Word-part flow with unique JPEGs, CAS before SMTP, fail-closed
uncertain send, all parts receipt, and recipient privacy.
"""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from delivery_bridge import complete_entry, validate_ledger
from monitor import article_id
from rasd_daily_volume_preflight_no_send import create_verified_daily_volumes
from rasd_daily_volume_delivery import (
    deliver_numbered_daily_volumes, verify_volume_manifest)

TO="review@example.com"
BAD_TO="ministry-not-approved@example.org"


class FakeLedger:
    def __init__(self):
        self.state={
            "schema_version":2,"entries":{},
            "approved_recipient_sha256":hashlib.sha256(
                TO.encode()).hexdigest()}
        self.version=1
        self.writes=0

    def read(self):
        return copy.deepcopy(self.state),str(self.version)

    def write(self,updated,sha):
        if sha!=str(self.version):
            raise RuntimeError("private_ledger_compare_and_swap_conflict")
        validate_ledger(updated)
        self.state=copy.deepcopy(updated)
        self.version+=1
        self.writes+=1

    def mark_smtp_accepted(self,key,receipt):
        state,sha=self.read()
        self.write(complete_entry(state,key,
                                  "2026-11-21T17:07:00+00:00",receipt),sha)


class NumberedDailySMTPWithoutNetwork(unittest.TestCase):
    MASTER="d"*24

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.ledger=FakeLedger()
        self.sent=[]

    def volumes(self):
        articles=[]
        digests=[]
        for i in range(4):
            photo=self.folder / f"publisher-original-{i}.jpg"
            pic=Image.effect_noise((900,700),90).convert("RGB")
            ImageDraw.Draw(pic).rectangle((20+i*55,70,60+i*55,110),
                                          fill=(i*42,20,120))
            pic.save(photo,"JPEG",quality=75)
            url=f"https://hapijournal.com/2026/11/21/no-send-test-{i}"
            articles.append({
                "id":article_id(url),"headline":f"وزارة التخطيط واختبار {i}",
                "source":"Hapi native news RSS","url":url,
                "publisher_excerpt":"اختبار صناعي محلي لا يرسل",
                "published_at_cairo":"2026-11-21 16:00 EET",
                "published_display_cairo":"21 نوفمبر 2026",
                "evidence_image_path":str(photo)})
            digests.append({
                "status":"verified",
                "sha256":hashlib.sha256(photo.read_bytes()).hexdigest()})
        return create_verified_daily_volumes(
            articles,digests,self.folder/"volumes",
            title="رصد | تجربة حجم بدون إرسال",
            start="20 نوفمبر 2026 22:00",end="21 نوفمبر 2026 22:00",
            max_word_bytes=1_200_000)

    def fake_smtp(self,word,*,sender,recipient,password,subject,key,body_text):
        self.assertEqual(recipient,TO)
        self.assertEqual(sender,"source@example.com")
        self.assertEqual(password,"offline-only")
        self.assertIn("الجزء",subject)
        self.assertIn("لا تكتمل",body_text)
        self.assertIn(self.MASTER,self.ledger.state["entries"])
        self.assertEqual(self.ledger.state["entries"][self.MASTER]["status"],
                         "reserved")
        self.assertTrue(all(self.ledger.state["entries"].get(k,{}).get("status")
                            in {"reserved","smtp_accepted"} for k in
                            self.ledger.state["entries"][self.MASTER]["part_keys"]))
        self.assertTrue(word.is_file())
        self.sent.append(key)
        return f"<rasd-{key}@gmail.com>"

    def send(self,volumes,recipient=TO,send=None):
        return deliver_numbered_daily_volumes(
            volumes,ledger=self.ledger,master_key=self.MASTER,
            sender="source@example.com",recipient=recipient,
            password="offline-only",title="رصد | التقرير المجمع اليومي",
            send_one_word=send or self.fake_smtp)

    def test_every_unique_part_is_reserved_before_first_send_and_receipted(self):
        volumes=self.volumes()
        self.assertGreater(len(volumes),1)
        result=self.send(volumes)
        self.assertEqual(result["status"],
                         "daily_volume_parts_smtp_accepted_unconfirmed_inbox")
        self.assertEqual(result["items"],4)
        self.assertEqual(result["parts"],len(volumes))
        self.assertFalse(result["inbox_delivery_verified"])
        self.assertEqual(len(set(self.sent)),len(volumes))
        master=self.ledger.state["entries"][self.MASTER]
        self.assertEqual(master["status"],"smtp_accepted")
        self.assertTrue(master["all_parts_smtp_accepted"])
        self.assertEqual(len(master["part_message_ids"]),len(volumes))
        self.assertTrue(all(self.ledger.state["entries"][key]["status"]
                            =="smtp_accepted" for key in self.sent))
        with self.assertRaisesRegex(RuntimeError,
                                    "daily_volume_plan_already_reserved"):
            self.send(volumes)
        self.assertEqual(len(self.sent),len(volumes))

    def test_uncertain_smtp_stops_and_never_automatically_resends(self):
        volumes=self.volumes()
        def sender(*args,**kwargs):
            if len(self.sent)==1:
                raise RuntimeError("smtp_uncertain_reconcile_sent_manually")
            return self.fake_smtp(*args,**kwargs)
        with self.assertRaisesRegex(RuntimeError,"smtp_uncertain"):
            self.send(volumes,send=sender)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.ledger.state["entries"][self.MASTER]["status"],
                         "reserved")
        accepted=sum(row.get("status")=="smtp_accepted"
                     for row in self.ledger.state["entries"].values())
        self.assertEqual(accepted,1)
        with self.assertRaisesRegex(RuntimeError,
                                    "daily_volume_plan_already_reserved"):
            self.send(volumes)
        self.assertEqual(len(self.sent),1)

    def test_other_recipient_blocked_before_writing_or_sending(self):
        volumes=self.volumes()
        with self.assertRaisesRegex(ValueError,
                                    "recipient_not_approved_by_private_ledger"):
            self.send(volumes,recipient=BAD_TO)
        self.assertEqual(self.ledger.writes,0)
        self.assertEqual(self.sent,[])

    def test_swapped_or_wrong_jpeg_sha_blocks_before_any_private_cas(self):
        volumes=self.volumes()
        volumes[0]["sha256"][0]="0"*64
        with self.assertRaisesRegex(RuntimeError,
                                    "daily_volume_original_image_mismatch_hold"):
            self.send(volumes)
        self.assertEqual(self.ledger.writes,0)
        self.assertEqual(self.sent,[])

    def test_numbered_part_must_not_silently_skip_part_two(self):
        volumes=self.volumes()
        volumes[1]["part"]=3
        with self.assertRaisesRegex(RuntimeError,
                                    "daily_volume_manifest_invalid"):
            self.send(volumes)
        self.assertEqual(self.ledger.writes,0)

    def test_bad_owner_recipient_or_changed_bytes_no_emails(self):
        volumes=self.volumes()
        volumes[0]["bytes"]+=1
        with self.assertRaisesRegex(RuntimeError,
                                    "daily_volume_attachment_size_hold"):
            self.send(volumes)
        self.assertEqual(self.ledger.writes,0)


if __name__=="__main__":
    unittest.main()
