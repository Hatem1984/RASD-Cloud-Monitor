"""Owner-gated daily numbered delivery dispatch: full 22:00 phase, no SMTP."""
import unittest
from datetime import datetime,timezone
from unittest.mock import MagicMock, patch

import scheduled_rasd as worker


class NumberedDailyScheduledGateNoSend(unittest.TestCase):
    NOW=datetime(2026,11,21,20,7,tzinfo=timezone.utc)
    NEWS={"id":"a"*24,"headline":"وزارة التخطيط في اختبار تجريبي"}

    def run(self,archive="true"):
        ledger=MagicMock()
        ledger.read.return_value=({"entries":{}},"sha")
        with patch.object(worker,"require_github_scheduler"),\
             patch.object(worker,"protected_credentials",
                          return_value=("news@example.com","owner@example.com",
                                        "offline",ledger)),\
             patch.object(worker,"news_for_rollup",
                          return_value=[self.NEWS]),\
             patch("daily_sent_consolidator.consolidate_sent_words",
                   return_value=([
                       {"path":"local-placeholder","count":1,"sha256":["x"]}],
                       [{"status":"verified","sha256":"x"}])) as consolidate,\
             patch("rasd_daily_volume_delivery.deliver_numbered_daily_volumes",
                   return_value={
                       "status":"daily_volume_owner_mock",
                       "parts":1,"smtp_accepted":False}) as delivery,\
             patch.object(worker,"send_one_word") as legacy,\
             patch.dict(worker.os.environ,{
                 "GITHUB_EVENT_NAME":"schedule",
                 "RASD_JOB_CRON":worker.DAILY_CRON,
                 "RASD_DAILY_VOLUME_DELIVERY_ENABLED":"true",
                 "RASD_DAILY_SENT_ARCHIVE_ENABLED":archive,
                 "RASD_REPORT_CC":"",
             }):
            if archive=="true":
                output=worker.run_scheduled("rollup",self.NOW)
                self.assertEqual(output["status"],"daily_volume_owner_mock")
                self.assertTrue(consolidate.call_args.kwargs["volume_preflight_only"])
                self.assertEqual(delivery.call_args.kwargs["master_key"],
                                 worker.digest_key("rollup:2026-11-21"))
                self.assertIs(delivery.call_args.kwargs["send_one_word"],
                              worker.send_one_word)
            else:
                with self.assertRaisesRegex(
                        RuntimeError,"daily_volume_requires_original_sent_archive"):
                    worker.run_scheduled("rollup",self.NOW)
                consolidate.assert_not_called()
                delivery.assert_not_called()
            legacy.assert_not_called()
            ledger.reserve.assert_not_called()

    def test_owner_approved_numbered_path_does_not_use_old_single_smtp(self):
        self.run()

    def test_cannot_send_new_daily_parts_without_original_sent_archive(self):
        self.run(archive="false")


if __name__=="__main__":
    unittest.main()
