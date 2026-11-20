"""Pre-release capacity audit for multiple real publisher coverages. NO SEND.

As total authenticated clippings rise, never silently drop older items or
pretend that a >60 daily report was sent; respect existing protected caps.
"""
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import scheduled_rasd as rasd
from monitor import article_id


def story(n, name, host):
    url=f"https://{host}/news/{n}"
    return {
        "id": article_id(url), "source":name,
        "url":url, "headline":f"وزارة التخطيط تناقش خطة التنمية رقم {n}",
        "published_at_cairo":f"2026-11-17 12:{n%60:02d} EET",
        "published_display_cairo":"17 نوفمبر 2026",
    }


class DeliveryCoverageStressNoSend(unittest.TestCase):
    def test_17_distinct_publisher_clips_only_15_admitted_per_slot(self):
        items=[story(i, "صحيفة أ" if i%2==0 else "صحيفة ب",
                     "paper-one.example" if i%2==0 else "paper-two.example")
               for i in range(17)]
        ledger=MagicMock()
        ledger.read.return_value=({"entries":{}},"fixture-sha")
        admitted=[]
        def prepare(stories,config,folder,**kwargs):
            admitted.extend(stories)
            destination=Path(folder)/"fixture-not-a-real-report.docx"
            destination.write_bytes(b"offline-test")
            return destination,stories,0,False
        with (
            patch.dict(os.environ,{
                "GITHUB_EVENT_NAME":"schedule","RASD_JOB_CRON":rasd.HALF_HOUR_CRON}),
            patch.object(rasd,"require_github_scheduler"),
            patch.object(rasd,"scheduled_phase",return_value="interval"),
            patch.object(rasd,"protected_credentials",
                         return_value=("from@example.invalid","to@example.invalid",
                                       "fake",ledger)),
            patch.object(rasd,"discover_interval_news",return_value=items),
            patch.object(rasd,"prepare_source_limited_verified_word",
                         side_effect=prepare),
            patch.object(rasd,"send_one_word",return_value="<rasd-fixture@gmail.com>") as smtp,
            patch.object(rasd,"reserve_stories") as reserve,
        ):
            answer=rasd.run_scheduled("interval", datetime(
                2026,11,17,10,35,tzinfo=timezone.utc))
        self.assertEqual(len(admitted),15)
        self.assertEqual(answer["waiting_approved_news"],2)
        self.assertEqual(answer["items"],15)
        self.assertEqual(len({a["source"] for a in admitted}),2)
        smtp.assert_called_once()
        reserve.assert_called_once()

    def test_nightly_exactly_60_verified_items_not_miscounted(self):
        name="Verified Publisher"
        config={"feeds":[{"name":name,
                           "allowed_article_hosts":["news.example"]}]}
        entries={}
        for i in range(60):
            s=story(i,name,"news.example")
            entries[s["id"]] = {
                "kind":"interval_item","status":"smtp_accepted",
                "accepted_at":"2026-11-17T15:00:00+02:00","news":s
            }
        accepted=rasd.news_for_rollup({"entries":entries},"2026-11-17",config)
        self.assertEqual(len(accepted),60)

    def test_168_actual_unique_acceptance_records_do_not_hit_old_60_limit(self):
        name="Verified Publisher"
        config={"feeds":[{"name":name,
                           "allowed_article_hosts":["news.example"]}]}
        entries={}
        for i in range(168):
            s=story(i,name,"news.example")
            entries[s["id"]]={
                "kind":"interval_item", "status":"smtp_accepted",
                "accepted_at":"2026-11-17T15:00:00+02:00",
                "news":s,
            }
        accepted=rasd.news_for_rollup({"entries":entries},"2026-11-17",config)
        self.assertEqual(len(accepted),168)
        self.assertEqual(len({x["id"] for x in accepted}),168)

    def test_nightly_181st_not_silently_discarded_or_sent(self):
        name="Verified Publisher"
        config={"feeds":[{"name":name,
                           "allowed_article_hosts":["news.example"]}]}
        entries={}
        for i in range(181):
            s=story(i,name,"news.example")
            entries[s["id"]]={
                "kind":"interval_item","status":"smtp_accepted",
                "accepted_at":"2026-11-17T15:00:00+02:00","news":s
            }
        with self.assertRaisesRegex(RuntimeError,
                                    "rollup_exceeds_180_verified_items_manual_review"):
            rasd.news_for_rollup({"entries":entries},"2026-11-17",config)


if __name__=="__main__":
    unittest.main()
