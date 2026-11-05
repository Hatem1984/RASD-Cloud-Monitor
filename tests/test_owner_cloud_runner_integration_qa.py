"""No-network integration of private approved settings -> existing SMTP runner, mocked mail.
The test intentionally NEVER opens network, sends mail, or mutates a private ledger.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import MagicMock,patch

from delivery_bridge import PrivateGitHubLedger
from monitor import article_id
import rasd_cloud_settings as cloud
import scheduled_rasd as run
from rasd_settings_bridge_qa import _hash

SOURCE=json.loads((Path(__file__).resolve().parent.parent/"sources_owner_daily_qa.json").read_text("utf-8"))
NOW=datetime(2026,11,3,10,37,tzinfo=run.CAIRO)
URL="https://hapijournal.com/owner-qa-original"
STORY={"id":article_id(URL),"headline":"وزير التخطيط يعقد اجتماعًا",
       "published_at_cairo":"2026-11-03 10:15 EET",
       "published_display_cairo":"3 نوفمبر 2026 الساعة 10:15",
       "publisher_excerpt":"","url":URL,"source":SOURCE["feeds"][0]["name"]}
TOPICS=[{"label":"وزير التخطيط","aliases":["وزير التخطيط"],"enabled":True,"match":"any"}]
OWNER={"topics":TOPICS,"sources":[{"id":f["id"],"name":f["name"],"url":f["url"],"enabled":True} for f in SOURCE["feeds"]],
       "start":"00:00","end":"22:00","report_title":"رصد | التجربة",
       "report_type":"شامل","detail":"متوسط","analysis_instructions":"",
       "include":{"headlines":True,"links":True,"screenshots":True,"analysis":True},
       "scan_minutes":30,"send_mode":"daily","send_at":"22:00","source_proposals":[]}
MANIFEST={"schema_version":1,"active_version":3,"settings":{k:OWNER[k] for k in ("topics","sources","start","end","report_title","report_type","detail","analysis_instructions","include","scan_minutes","send_mode","send_at")},
          "sha256":_hash({k:OWNER[k] for k in ("topics","sources","start","end","report_title","report_type","detail","analysis_instructions","include","scan_minutes","send_mode","send_at")}),
          "scope":"ACTIVE_APPROVED"}
MAIL="<rasd-aaaaaaaaaaaaaaaaaaaaaaaa@gmail.com>"

class OwnerRunner(unittest.TestCase):
    def test_cloud_loader_fails_closed_and_requires_activation(self):
        base=SOURCE
        config,metadata=cloud.load_owner_active_config(base,environ={})
        self.assertIs(config,base);self.assertIsNone(metadata)
        with patch.object(cloud,"private_active_config",return_value=MANIFEST):
            effective,m=cloud.load_owner_active_config(base,
                environ={"RASD_OWNER_SETTINGS_ENABLED":"true",
                         "RASD_PRIVATE_LEDGER_TOKEN":"x"*50})
        self.assertEqual(len(effective["feeds"]),13)
        self.assertEqual(effective["keywords"],["وزير التخطيط"])
        self.assertEqual(m["active_version"],3)
        bad={**MANIFEST,"scope":"QA_PREVIEW_NO_SEND"}
        with patch.object(cloud,"private_active_config",return_value=bad):
            with self.assertRaisesRegex(RuntimeError,"not_production_approved"):
                cloud.load_owner_active_config(base,
                    environ={"RASD_OWNER_SETTINGS_ENABLED":"true",
                             "RASD_PRIVATE_LEDGER_TOKEN":"x"*50})
    def _run(self,storylist,state=None,clock=NOW,mode="interval",verified=True):
        ledger=MagicMock()
        ledger.read.return_value=(state or {"entries":{}},"sha")
        cfg={**SOURCE,"keywords":["وزير التخطيط"]}
        def discover(conf,when,**kwargs):
            kwargs["source_records"].extend({"feed_id":f["id"],"status":"ok","verified_links":10} for f in SOURCE["feeds"])
            return storylist
        def prepare(stories,cfg,out,**kwargs):
            return Path(out)/"QA-test-only.docx",stories,0,False
        env={"GITHUB_EVENT_NAME":"schedule","RASD_JOB_CRON":run.HALF_HOUR_CRON,
             "RASD_SMART_NO_EMPTY_INTERVAL_EMAIL":"true",
             "RASD_PRIVATE_LEDGER_TOKEN":"x"*40}
        with (patch.object(run,"require_github_scheduler"),
              patch.object(run,"protected_credentials",return_value=("sender@gmail.com","ministry@example.com","test-not-used",ledger)),
              patch.object(run,"scheduled_phase",return_value="interval" if mode=="interval" else "rollup"),
              patch.object(run,"discover_interval_news",side_effect=discover),
              patch.object(run,"prepare_source_limited_verified_word",side_effect=prepare) as images,
              patch.object(run,"reserve_stories") as reserve,
              patch("rasd_owner_evidence_journal.PrivateDayJournal.record",return_value={}),
              patch.object(run,"send_one_word",return_value=MAIL) as send,
              patch.object(cloud,"load_owner_active_config",return_value=(cfg,MANIFEST)),
              patch.dict(run.os.environ,env,clear=False)):
            result=run.run_scheduled(mode,clock)
        return result,reserve,send,ledger,images
    def test_one_verified_news_uses_period_reservation_and_acceptance(self):
        result,reserve,send,ledger,_=self._run([STORY])
        self.assertEqual(result["items"],1)
        self.assertEqual(reserve.call_count,1)
        self.assertRegex(reserve.call_args.kwargs["slot_key"],"^[a-f0-9]{24}$")
        self.assertEqual(send.call_count,1)
        self.assertEqual(ledger.mark_smtp_accepted_many.call_count,1)
        self.assertEqual(ledger.mark_smtp_accepted_many.call_args.kwargs["slot_key"],
                         reserve.call_args.kwargs["slot_key"])
    def test_nothing_new_no_mail_and_no_reservation(self):
        result,reserve,send,ledger,images=self._run([])
        self.assertEqual(result["status"],"NO_NEW_VERIFIED_NEWS")
        reserve.assert_not_called();send.assert_not_called();images.assert_not_called()
    def test_pre_reserved_slot_never_sends_even_when_news_appears(self):
        slot,_day,_start=run.cairo_window(NOW)
        reserved=run.digest_key("interval-slot:"+slot)
        result,reserve,send,ledger,images=self._run([STORY],state={"entries":{reserved:{"status":"reserved"}}})
        self.assertEqual(result["status"],"interval_slot_already_reserved_or_sent")
        reserve.assert_not_called();send.assert_not_called();images.assert_not_called()
    def test_after_22_not_sent_and_not_captured(self):
        result,reserve,send,ledger,images=self._run([STORY],
            clock=datetime(2026,11,3,22,37,tzinfo=run.CAIRO))
        self.assertEqual(result["status"],"owner_after_daily_cutoff_no_interval_mail")
        reserve.assert_not_called();send.assert_not_called();images.assert_not_called()
    def test_owner_day_zero_news_does_not_email_empty_status(self):
        ledger=MagicMock()
        ledger.read.return_value=({"entries":{}},"sha")
        with (patch.object(run,"require_github_scheduler"),
              patch.object(run,"protected_credentials",return_value=("sender@gmail.com","ministry@example.com","test",ledger)),
              patch.object(run,"scheduled_phase",return_value="rollup"),
              patch.object(run,"news_for_owner_calendar_rollup",return_value=[]),
              patch("rasd_owner_evidence_journal.PrivateDayJournal.read",return_value=({"slots":{}},None)),
              patch("rasd_owner_daily_closeout.prepare_owner_closeout",return_value={"status":"NO_NEW_VERIFIED_NEWS_NO_DAILY_EMAIL"}),
              patch.object(run,"send_one_word") as send,
              patch.object(cloud,"load_owner_active_config",return_value=(SOURCE,MANIFEST)),
              patch.dict(run.os.environ,{"GITHUB_EVENT_NAME":"schedule","RASD_JOB_CRON":run.DAILY_CRON,
                      "RASD_PRIVATE_LEDGER_TOKEN":"x"*40},clear=False)):
            result=run.run_scheduled("rollup",datetime(2026,11,3,22,8,tzinfo=run.CAIRO))
        self.assertEqual(result["status"],"NO_NEW_VERIFIED_NEWS_NO_DAILY_EMAIL")
        send.assert_not_called()
        ledger.reserve.assert_not_called()
    def test_atomic_period_reservation_is_written_with_article(self):
        state={"schema_version":2,"entries":{},"approved_recipient_sha256":"0"*64}
        ledger=MagicMock()
        ledger.read.return_value=(state,"prior-sha")
        slot=run.digest_key("interval-slot:2026-11-03T08:30Z")
        run.reserve_stories(ledger,[STORY],"2026-11-03",slot_key=slot)
        saved=ledger.write.call_args.args[0]
        self.assertEqual(saved["entries"][slot]["kind"],"interval_slot")
        self.assertEqual(saved["entries"][slot]["article_ids"],[STORY["id"]])
        self.assertEqual(saved["entries"][STORY["id"]]["kind"],"interval_item")
        self.assertEqual(ledger.write.call_count,1)
        obj=PrivateGitHubLedger("x"*40)
        obj.read=lambda:(saved,"sha")
        obj.write=MagicMock()
        obj.mark_smtp_accepted_many([STORY["id"]],MAIL,slot_key=slot)
        updated=obj.write.call_args.args[0]
        self.assertEqual(updated["entries"][slot]["status"],"smtp_accepted")
        self.assertEqual(updated["entries"][STORY["id"]]["status"],"smtp_accepted")
        self.assertEqual(updated["entries"][slot]["message_id"],MAIL)
    def test_calendar_rollup_excludes_previous_day_even_if_accepted_today(self):
        old={**STORY,"id":article_id("https://hapijournal.com/old"),
             "url":"https://hapijournal.com/old",
             "published_at_cairo":"2026-11-02 23:45 EET"}
        entries={x["id"]:{"kind":"interval_item","status":"smtp_accepted",
                          "news":x,"accepted_at":"2026-11-03T09:00:00+00:00"}
                 for x in (STORY,old)}
        result=run.news_for_owner_calendar_rollup({"entries":entries},"2026-11-03",SOURCE)
        self.assertEqual([x["id"] for x in result],[STORY["id"]])
if __name__=="__main__":unittest.main()
