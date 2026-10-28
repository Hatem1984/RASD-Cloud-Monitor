"""Opt-in MA'AL/RASD 30min no-empty email policy: runnable integration QA only."""
import io,unittest
from datetime import datetime,timezone
from unittest.mock import MagicMock,patch
import scheduled_rasd as rasd

class SmartNoEmptyInterval(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,27,11,37,tzinfo=timezone.utc)
  self.config={"feeds":[{"id":"ministry"},{"id":"hapi"}]}
  self.good=[{"feed_id":"ministry","status":"ok","verified_links":8},
             {"feed_id":"hapi","status":"failed","verified_links":0}]
  self.ledger=MagicMock()
  self.ledger.read.return_value=({"entries":{}},"hash")
 def call(self,stories,blocked=False,active="true"):
  def source_stub(config,now,**kwargs):
   kwargs["source_records"].extend(self.good)
   return stories
  scope={
   "RASD_SMART_NO_EMPTY_INTERVAL_EMAIL":active,
   "GITHUB_EVENT_NAME":"schedule",
   "RASD_JOB_CRON":rasd.HALF_HOUR_CRON,
  }
  with (patch.object(rasd.json,"loads",return_value=self.config),
        patch.object(rasd,"require_github_scheduler"),
        patch.object(rasd,"protected_credentials",return_value=(
          "test@example.invalid","review@example.invalid","none",self.ledger)),
        patch.object(rasd,"discover_interval_news",side_effect=source_stub),
        patch.object(rasd,"prepare_source_limited_verified_word",
          side_effect=RuntimeError("no_original_publisher_page_verified")) as capture,
        patch.object(rasd,"send_empty_interval_status") as legacy_mail,
        patch.object(rasd,"send_one_word") as send,
        patch.object(rasd,"reserve_stories") as reserve,
        patch.object(rasd,"scheduled_phase",return_value="interval"),
        patch.dict(rasd.os.environ,scope)):
   result=rasd.run_scheduled("interval",self.now)
  assert not legacy_mail.called and not send.called and not reserve.called
  self.ledger.reserve.assert_not_called()
  self.ledger.mark_smtp_accepted.assert_not_called()
  self.ledger.mark_smtp_accepted_many.assert_not_called()
  return result,capture
 def test_empty_news_no_mail_cas(self):
  result,capture=self.call([])
  self.assertEqual(result["status"],"NO_NEW_VERIFIED_NEWS")
  self.assertFalse(result["smtp_accepted"])
  self.assertEqual(result["sources_failed"],1)
  self.assertEqual(result["sources_checked"],2)
  capture.assert_not_called()
 def test_source_image_hold_no_mail_retry_eligible(self):
  story={"id":"a"*24,"headline":"test","published_at_cairo":"2026-10-27 14:30 EEST"}
  result,capture=self.call([story])
  self.assertEqual(result["status"],"EVIDENCE_HOLD")
  self.assertEqual(result["held_articles"],1)
  self.assertFalse(result["cas_mutated"])
  capture.assert_called_once()
 def test_repeated_empty_ticks_never_reserve(self):
  for _ in range(3):self.assertEqual(self.call([])[0]["items"],0)
  self.ledger.read.assert_called()
  self.ledger.reserve.assert_not_called()
 def test_different_health_status_partial(self):
  result=self.call([])[0]
  self.assertEqual(result["coverage_status"],"PARTIAL")
 def test_malformed_health_fails_closed(self):
  with self.assertRaisesRegex(RuntimeError,"source_health_metadata"):
   rasd.smart_interval_no_mail(config=self.config,
    health=[{"feed_id":"ministry","status":"ok"}],window="2026-10-27T11:30Z")
 def test_negative_hold_fails_closed(self):
  with self.assertRaisesRegex(RuntimeError,"interval_status_invalid_hold_count"):
   rasd.smart_interval_no_mail(config=self.config,health=self.good,
    window="2026-10-27T11:30Z",held_articles=-1)
 def test_daily_2200_dst_unchanged(self):
  for instant in [datetime(2026,7,5,19,0,tzinfo=timezone.utc),
                   datetime(2026,11,5,20,0,tzinfo=timezone.utc)]:
   self.assertEqual(rasd.scheduled_phase(rasd.DAILY_CRON,instant),"rollup")
 def test_half_hour_2200_collision_skipped(self):
  self.assertEqual(rasd.scheduled_phase(rasd.HALF_HOUR_CRON,
    datetime(2026,7,5,19,7,tzinfo=timezone.utc)),"skip")
if __name__=="__main__":unittest.main()
