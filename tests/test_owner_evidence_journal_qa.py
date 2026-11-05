"""Private 30m RSS observations are verifiable, durable and cannot invent completeness."""
import copy
from datetime import date,datetime
import unittest
from monitor import article_id
from daily_report import CAIRO
from rasd_owner_evidence_journal import new_day,add_observation,validate_journal,audit_day

DAY=date(2026,11,3)
FEEDS=["hapi","shorouk"]
SOURCE=[{"feed_id":"hapi","status":"ok"},{"feed_id":"shorouk","status":"ok"}]
URL="https://hapijournal.com/qa-only-news"
STORY={"id":article_id(URL),"headline":"وزير التخطيط يعلن خطة تنمية",
       "url":URL,"source":"Hapi native news RSS",
       "published_at_cairo":"2026-11-03 00:10 EET",
       "published_display_cairo":"2026-11-03 00:10 القاهرة",
       "publisher_excerpt":""}
def add(t="00:01",health=None,stories=None,prior=None):
    h,m=map(int,t.split(":"))
    return add_observation(prior or new_day(DAY),
        now=datetime(2026,11,3,h,m,tzinfo=CAIRO),
        source_health=health or SOURCE,candidate_stories=stories or [],
        expected_source_ids=FEEDS,config_version=27)

class JournalSecurity(unittest.TestCase):
    def test_one_slot_has_distinct_stable_candidates(self):
        j=add(stories=[STORY])
        self.assertEqual(len(j["slots"]),1)
        self.assertEqual(len(j["articles"]),1)
        self.assertEqual(j["slots"]["00:00"]["candidate_ids"],[STORY["id"]])
        self.assertEqual(audit_day(j,DAY,FEEDS)["complete"],False)
    def test_repeat_same_slot_does_not_drop_earlier_candidate(self):
        j=add(stories=[STORY])
        j=add("00:15",stories=[],prior=j)
        self.assertEqual(j["slots"]["00:00"]["candidate_ids"],[STORY["id"]])
        self.assertEqual(j["slots"]["00:00"]["sources"]["hapi"],"ok")
    def test_ambiguous_item_identity_cannot_replace_existing_story(self):
        j=add(stories=[STORY])
        altered={**STORY,"headline":"محتوى مختلف"}
        with self.assertRaisesRegex(ValueError,"changed_story_identity"):
            add("00:17",stories=[altered],prior=j)
    def test_false_nonmatching_url_fails_before_private_write(self):
        with self.assertRaisesRegex(ValueError,"journal_candidate_id"):
            add(stories=[{**STORY,"url":"https://not-the-original.example/"}])
    def test_falsely_backdated_source_slot_fails(self):
        j=add(stories=[STORY])
        changed=copy.deepcopy(j)
        changed["slots"]["00:00"]["observed_at_utc"]="2026-11-03T14:15:00+00:00"
        with self.assertRaisesRegex(ValueError,"observation_clock"):
            validate_journal(changed,DAY)
    def test_missing_source_record_fails_before_private_write(self):
        with self.assertRaisesRegex(ValueError,"journal_source_inventory"):
            add(health=SOURCE[:-1])
    def test_failed_source_cannot_be_labeled_complete(self):
        j=add(health=[SOURCE[0],{"feed_id":"shorouk","status":"failed"}])
        a=audit_day(j,DAY,FEEDS)
        self.assertFalse(a["complete"])
        self.assertIn("00:00",a["failed_slots"])
    def test_wrong_cairo_day_holds(self):
        j=add()
        with self.assertRaisesRegex(ValueError,"journal_shape"):
            validate_journal(j,date(2026,11,2))
if __name__=="__main__":
    unittest.main()
