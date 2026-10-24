"""Large RSS discovery never blocks all safely deliverable press news."""
import os
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import MagicMock,patch
import scheduled_rasd as worker

class SafeNewsBacklog(unittest.TestCase):
    def test_oldest_fifteen_first_remaining_two_wait_for_next_scan(self):
        articles=[{
            "id":f"{i+1:024x}",
            "headline":f"Distinct planning event with evidence item {i}",
            "source":"Alborsa native Egyptian Economy RSS",
            "url":f"https://www.alborsaanews.com/2026/10/24/{2000000+i}",
            "publisher_excerpt":"",
            "published_at_cairo":f"2026-10-24 13:{i:02d} EEST",
            "published_display_cairo":"24 October 2026"
        } for i in range(17)]
        ledger=MagicMock()
        ledger.read.return_value=({"entries":{}},"old-sha")
        captured=[]
        def prepare(items,*args,**kwargs):
            captured.extend(items)
            d=Path(args[1])/"qa-original.docx"
            d.write_bytes(b"offline test no email")
            return d,items,0,False
        with (
            patch.dict(os.environ,{"GITHUB_EVENT_NAME":"schedule",
                                   "RASD_JOB_CRON":worker.HALF_HOUR_CRON}),
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"scheduled_phase",return_value="interval"),
            patch.object(worker,"protected_credentials",
                         return_value=("from@gmail.com","to@gmail.com","fake",ledger)),
            patch.object(worker,"discover_interval_news",return_value=articles),
            patch.object(worker,"prepare_source_limited_verified_word",
                         side_effect=prepare),
            patch.object(worker,"reserve_stories") as reserve,
            patch.object(worker,"send_one_word",return_value="<rasd-offline@gmail.com>") as email,
        ):
            answer=worker.run_scheduled("interval",datetime(
                2026,10,24,11,35,tzinfo=timezone.utc))
        self.assertEqual(len(captured),15)
        self.assertEqual([a["id"] for a in captured],
                         [a["id"] for a in articles[:15]])
        self.assertEqual(answer["waiting_approved_news"],2)
        self.assertEqual(answer["items"],15)
        self.assertTrue(answer["source_limited"])
        email.assert_called_once()
        reserve.assert_called_once()
        self.assertEqual(ledger.mark_smtp_accepted_many.call_count,1)

if __name__=="__main__":
    unittest.main()
