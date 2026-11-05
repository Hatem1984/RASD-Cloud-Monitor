"""QA no-network versioned config bridge / private cloud reader contracts."""
import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import rasd_settings_bridge_qa as bridge
import rasd_private_settings_reader_qa as remote

ROOT=Path(__file__).resolve().parent.parent
BASELINE=json.loads((ROOT/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))

def settings():
    return {
        "topics":[{"label":"وزير التخطيط","aliases":["وزير التخطيط"],"enabled":True,"match":"any"},
                  {"label":"وزير + بنك","aliases":["وزير التخطيط","بنك الاستثمار القومي"],"enabled":True,"match":"all"}],
        "sources":[{"id":r["id"],"name":r["name"],"url":r["url"],"enabled":True} for r in BASELINE["feeds"]],
        "start":"00:00","end":"22:00","report_title":"رصد | اليوم",
        "report_type":"شامل","detail":"متوسط","analysis_instructions":"",
        "include":{"headlines":True,"links":True,"screenshots":True,"analysis":True},
        "scan_minutes":30,"send_mode":"daily","send_at":"22:00",
        "source_proposals":[]}

class SettingsCloudBridge(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.file=Path(t.name)/"state.db"
        c=sqlite3.connect(self.file)
        c.execute("CREATE TABLE settings(slot TEXT PRIMARY KEY,version INTEGER,payload TEXT NOT NULL)")
        c.execute("INSERT INTO settings VALUES(?,?,?)",("active",12,json.dumps(settings(),ensure_ascii=False)))
        c.execute("INSERT INTO settings VALUES(?,?,?)",("draft",13,json.dumps(settings(),ensure_ascii=False)))
        c.commit();c.close()
    def replace(self,slot,value,version):
        c=sqlite3.connect(self.file)
        try:
            c.execute("UPDATE settings SET payload=?,version=? WHERE slot=?",(json.dumps(value,ensure_ascii=False),version,slot))
            c.commit()
        finally:
            c.close()
    def test_uses_active_not_draft_and_versioned_snapshot(self):
        draft=settings();draft["topics"]=[{"label":"اختبار","aliases":["مصطلح تجريبي"],"match":"any","enabled":True}]
        self.replace("draft",draft,99)
        snap=bridge.active_snapshot_from_db(self.file,BASELINE)
        self.assertEqual(snap["active_version"],12)
        self.assertEqual(snap["settings"]["topics"][0]["label"],"وزير التخطيط")
        self.assertNotIn("email_display",snap["settings"])
        self.assertEqual(len(snap["sha256"]),64)
        self.assertEqual(bridge.scanned_config(snap,BASELINE)["keywords"][:1],["وزير التخطيط"])
    def test_active_change_updates_qa_bridge_but_not_draft(self):
        orig=bridge.active_snapshot_from_db(self.file,BASELINE)
        changed=settings();changed["sources"][0]["enabled"]=False
        self.replace("active",changed,20)
        new=bridge.active_snapshot_from_db(self.file,BASELINE)
        self.assertNotEqual(orig["sha256"],new["sha256"])
        self.assertEqual(new["active_version"],20)
        self.assertEqual(len(bridge.scanned_config(new,BASELINE)["feeds"]),12)
        self.assertEqual(len(BASELINE["feeds"]),13)
    def test_proposed_source_never_enters_active_feeds(self):
        s=settings()
        s["source_proposals"]=[{"name":"Source candidate","url":"https://publisher.example.org/feed/","status":"PENDING_REVIEW"}]
        self.replace("active",s,21)
        snap=bridge.active_snapshot_from_db(self.file,BASELINE)
        self.assertEqual(len(bridge.scanned_config(snap,BASELINE)["feeds"]),13)
        self.assertNotIn("source_proposals",snap["settings"])
    def test_unknown_active_feed_fails_even_when_suggested(self):
        s=settings()
        s["sources"].append({"id":"new","name":"Unapproved","url":"https://other.example/feed","enabled":True})
        self.replace("active",s,21)
        with self.assertRaisesRegex(ValueError,"approved_source_inventory_mismatch"):
            bridge.active_snapshot_from_db(self.file,BASELINE)
    def test_or_first_pass_then_all_group_enforced(self):
        s=settings()
        only=[{"headline":"وزير التخطيط يلتقي وفدًا","publisher_excerpt":""}]
        self.assertEqual(len(bridge.filter_owner_topic_matches(only,s)),1)
        s["topics"][0]["enabled"]=False
        self.assertEqual(bridge.filter_owner_topic_matches(only,s),[])
        two=[{"headline":"وزير التخطيط يناقش بنك الاستثمار القومي","publisher_excerpt":""}]
        self.assertEqual(len(bridge.filter_owner_topic_matches(two,s)),1)
    def test_tampered_cloud_manifest_or_public_scope_fails(self):
        snap=bridge.active_snapshot_from_db(self.file,BASELINE)
        with self.assertRaisesRegex(ValueError,"nonactive_cloud_settings"):
            bridge.verify_cloud_ready_manifest(snap,BASELINE)
        snap["scope"]="ACTIVE_APPROVED"
        bridge.verify_cloud_ready_manifest(snap,BASELINE)
        snap["settings"]["topics"][0]["aliases"]=["عشوائي"]
        with self.assertRaisesRegex(ValueError,"cloud_settings_digest_mismatch"):
            bridge.verify_cloud_ready_manifest(snap,BASELINE)
    def test_private_cloud_fetch_with_mock_only(self):
        snap=bridge.active_snapshot_from_db(self.file,BASELINE)
        snap["scope"]="ACTIVE_APPROVED"
        raw=json.dumps(snap,ensure_ascii=False).encode("utf-8")
        calls=[]
        def mocked(url):
            calls.append(url)
            if "/contents/" not in url:
                return {"private":True,"full_name":"ApprovedOwner/rasd-private-config"}
            return {"type":"file","encoding":"base64","content":base64.b64encode(raw).decode(),
                    "size":len(raw)}
        data=remote.private_active_config(repository="ApprovedOwner/rasd-private-config",
                 path="rasd/active.json",ref="main",token="x"*40,baseline=BASELINE,
                 api_get=mocked)
        self.assertEqual(data["active_version"],12)
        self.assertEqual(len(calls),2)
        with self.assertRaisesRegex(RuntimeError,"repository_not_approved"):
            remote.private_active_config(repository="Hatem1984/RASD-Cloud-Monitor",
                path="rasd/active.json",ref="main",token="x"*40,baseline=BASELINE,
                api_get=mocked)
    def test_nonprivate_or_missing_token_holds(self):
        with self.assertRaisesRegex(RuntimeError,"secret_missing"):
            remote.private_active_config(repository="ApprovedOwner/private-r",
                path="rasd/active.json",ref="main",token="",baseline=BASELINE)
        with self.assertRaisesRegex(RuntimeError,"visibility_hold"):
            remote.private_active_config(repository="ApprovedOwner/private-r",
                path="rasd/active.json",ref="main",token="x"*40,baseline=BASELINE,
                api_get=lambda u:{"private":False,"full_name":"ApprovedOwner/private-r"})
if __name__=="__main__":unittest.main()
