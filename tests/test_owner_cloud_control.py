"""Owner control is an exact protected entry point, no network or real mail."""
import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from pathlib import Path
import scheduled_rasd as s

NOW=datetime(2026,11,25,20,40,tzinfo=timezone.utc)
BASE={
 "GITHUB_REF":"refs/heads/main","GITHUB_REPOSITORY":"Hatem1984/RASD-Cloud-Monitor",
 "GITHUB_RUN_ATTEMPT":"1","GITHUB_RUN_ID":"123","GITHUB_EVENT_NAME":"workflow_dispatch",
 "GITHUB_WORKFLOW_REF":s.OWNER_CONTROL_WORKFLOW,"GITHUB_ACTOR":"Hatem1984",
 "RASD_AUTOMATION_ENABLED":"true","RASD_OWNER_CONTROL_ENABLED":"true",
 "RASD_OWNER_CONTROL_CONFIRM":"CONFIRM_CURRENT_RASD_DELIVERY",
 "RASD_JOB_CRON":s.OWNER_CONTROL_MARKER,"RASD_OWNER_CONTROL_ACTION":"interval",
 "RASD_OWNER_CONTROL_REQUESTED_AT":NOW.isoformat()
}
class OwnerControl(unittest.TestCase):
 def test_exact_request(self):
  with patch.dict(os.environ,BASE,clear=True):
   self.assertEqual(s.require_owner_control(NOW),"interval")
 def test_all_auth_boundaries(self):
  for key,bad in [
    ("GITHUB_ACTOR","other"),("GITHUB_REF","refs/heads/review"),("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_RUN_ID","bad"),("GITHUB_REPOSITORY","other/repo"),
    ("GITHUB_EVENT_NAME","schedule"),("GITHUB_WORKFLOW_REF",s.CLOUDFLARE_WORKFLOW),
    ("RASD_AUTOMATION_ENABLED","false"),("RASD_OWNER_CONTROL_ENABLED","false"),
    ("RASD_AUTOMATION_PAUSED","true"),("RASD_OWNER_CONTROL_CONFIRM",""),
    ("RASD_JOB_CRON",s.HALF_HOUR_CRON),("RASD_OWNER_CONTROL_ACTION","rollup_owner_once"),
    ("RASD_OWNER_CONTROL_REQUESTED_AT",(NOW-timedelta(minutes=16)).isoformat()),
    ("RASD_OWNER_CONTROL_REQUESTED_AT",(NOW+timedelta(minutes=1)).isoformat()),
    ("RASD_OWNER_CONTROL_REQUESTED_AT","2026-11-25T20:40:00")]:
   with self.subTest(key=key),patch.dict(os.environ,{**BASE,key:bad},clear=True):
    with self.assertRaises(RuntimeError):s.require_owner_control(NOW)
 def test_mode_mismatch_before_credentials(self):
  with patch.dict(os.environ,BASE,clear=True),patch.object(s,"datetime") as dt,patch.object(s,"protected_credentials") as creds:
   dt.now.return_value=NOW;dt.fromisoformat.side_effect=datetime.fromisoformat;dt.combine.side_effect=datetime.combine
   with self.assertRaisesRegex(RuntimeError,"owner_control_mode_mismatch"):
    s.run_scheduled("rollup_recovery",NOW)
   creds.assert_not_called()
 def test_manual_interval_respects_daily_boundary(self):
  now=NOW.replace(minute=10)
  with patch.dict(os.environ,{**BASE,"RASD_OWNER_CONTROL_REQUESTED_AT":now.isoformat()},clear=True),patch.object(s,"datetime") as dt,patch.object(s,"protected_credentials") as creds:
   dt.now.return_value=now;dt.fromisoformat.side_effect=datetime.fromisoformat;dt.combine.side_effect=datetime.combine
   self.assertEqual(s.run_scheduled("interval",now)["status"],"skip_non_target_cairo_slot")
   creds.assert_not_called()
 def test_manual_recovery_does_not_replay_old_daily(self):
  now=NOW.replace(hour=10)
  env={**BASE,"RASD_OWNER_CONTROL_ACTION":"rollup_recovery","RASD_OWNER_CONTROL_REQUESTED_AT":now.isoformat()}
  with patch.dict(os.environ,env,clear=True),patch.object(s,"datetime") as dt,patch.object(s,"protected_credentials") as creds:
   dt.now.return_value=now;dt.fromisoformat.side_effect=datetime.fromisoformat;dt.combine.side_effect=datetime.combine
   self.assertEqual(s.run_scheduled("rollup_recovery",now)["status"],"expired_daily_recovery_requires_owner_review")
   creds.assert_not_called()
 def test_same_workflow_lock_and_existing_engine(self):
  text=(Path(__file__).resolve().parents[1]/".github/workflows/rasd-owner-control.yml").read_text(encoding="utf-8")
  self.assertIn("group: rasd-scheduled-monitor-private-ledger",text)
  self.assertIn("cancel-in-progress: false",text)
  self.assertIn("environment: rasd-production",text)
  self.assertIn("vars.RASD_OWNER_CONTROL_ENABLED == 'true'",text)
  self.assertIn("python scheduled_rasd.py --mode",text)
  self.assertNotIn("digest_mailer.py",text)
if __name__=="__main__":unittest.main()
