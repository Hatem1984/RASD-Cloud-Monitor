"""Enterprise roles, tenant-scoped direct downloads and reopen persisted DB."""
import hashlib
import json
import tempfile
import threading
import unittest
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
from http.cookiejar import CookieJar
from pathlib import Path
from docx import Document
from urllib.error import HTTPError
from urllib.request import Request,build_opener,HTTPCookieProcessor
from unittest.mock import patch

from rasd_app.server import App


def payload(data):
    return json.dumps(data).encode("utf-8")


class RoleHTTPAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app=App(self.tmp.name,live_only=True)
        st=self.app.store
        st.create_user("owner@private.test","owner-private-pass-2026",owner=True)
        self.a=st.create_tenant("جهة ألف",includes=["المالية"])
        self.b=st.create_tenant("جهة باء",includes=["الجامعة"])
        st.add_member(self.a,"admin-a@private.test","admin-a-private-pass","tenant_admin")
        st.add_member(self.a,"analyst-a@private.test","analyst-a-private-pass","analyst")
        st.add_member(self.a,"reader-a@private.test","reader-a-private-pass","reader")
        st.add_member(self.b,"admin-b@private.test","admin-b-private-pass","tenant_admin")
        st.add_source(self.a,"حابي","https://hapijournal.com/feed/")
        sid,_=st.start_scan(self.a)
        item={"title":"وزير المالية يعلن مشروعًا جديدًا","publisher":"hapijournal.com",
              "url":"https://hapijournal.com/qa/enterprise-unique",
              "published":(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()}
        with patch("rasd_app.enterprise.parse_live_feed",return_value=[item]):
            st.run_scan(self.a,sid)
        self.art=st.articles(self.a)[0]
        st.review(self.a,self.art["id"],"admin-a@private.test","approved",reason="مراجعة المصدر")
        start=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        end=datetime.now(timezone.utc).isoformat()
        self.report=st.create_report(self.a,[self.art["id"]],start,end)
        text=" ".join(p.text for p in Document(self.report["file_path"]).paragraphs)
        assert "مقارنة بالهدف: اختار المحلل" in text
        assert "نافذة آخر فحص RSS للجهة" in text
        self.server=ThreadingHTTPServer(("127.0.0.1",0),self.app.handler())
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base="http://127.0.0.1:"+str(self.server.server_port)

    def login(self,email,password):
        opener=build_opener(HTTPCookieProcessor(CookieJar()))
        req=Request(self.base+"/api/login",data=payload({"email":email,"password":password}),
                    headers={"Content-Type":"application/json"})
        with opener.open(req) as response:
            csrf=json.loads(response.read())["csrf"]
        return opener,csrf

    def get(self,opener,tenant,tail):
        return opener.open(self.base+"/api/tenants/"+tenant+tail)

    def post(self,opener,csrf,tenant,tail,data):
        return opener.open(Request(self.base+"/api/tenants/"+tenant+tail,
             data=payload(data),headers={"Content-Type":"application/json","X-RASD-CSRF":csrf}))

    def test_manager_analyst_reader_and_other_tenant(self):
        admin,adcsrf=self.login("admin-a@private.test","admin-a-private-pass")
        analyst,ancsrf=self.login("analyst-a@private.test","analyst-a-private-pass")
        reader,rdcsrf=self.login("reader-a@private.test","reader-a-private-pass")
        other,otcsrf=self.login("admin-b@private.test","admin-b-private-pass")
        with self.post(admin,adcsrf,self.a,"/settings",{"name":"جهة ألف المعتمدة"}) as r:
            self.assertEqual(r.status,200)
        with self.post(analyst,ancsrf,self.a,
              "/articles/"+self.art["id"]+"/review",{"state":"approved","reason":"تأكيد ثان"}) as r:
            self.assertEqual(r.status,200)
        with self.assertRaises(HTTPError) as e:
            self.post(analyst,ancsrf,self.a,"/settings",{"name":"ممنوع"})
        self.assertEqual(e.exception.code,403);e.exception.close()
        with self.assertRaises(HTTPError) as e:
            self.post(reader,rdcsrf,self.a,"/articles/"+self.art["id"]+"/review",{"state":"rejected","reason":"منع"})
        self.assertEqual(e.exception.code,403);e.exception.close()
        with self.assertRaises(HTTPError) as e:
            self.post(reader,rdcsrf,self.a,"/scan",{})
        self.assertEqual(e.exception.code,403);e.exception.close()
        with self.get(reader,self.a,"/articles") as r:
            self.assertEqual(len(json.loads(r.read())["articles"]),1)
        target="/reports/"+self.report["id"]+"/download"
        with self.get(reader,self.a,target) as r:
            self.assertEqual(hashlib.sha256(r.read()).hexdigest(),self.report["file_sha"])
        scan_id=self.app.store.list_scans(self.a)[0]["id"]
        for protected in (target,"/dashboard","/sources","/scans",
                          "/scans/"+scan_id,
                          "/articles","/articles?event_key="+self.art["event_key"],
                          "/articles/"+self.art["id"],
                          "/articles/"+self.art["id"]+"/image",
                          "/reports","/reports/"+self.report["id"],"/logo"):
            with self.subTest(protected=protected),self.assertRaises(HTTPError) as e:
                self.get(other,self.a,protected)
            self.assertEqual(e.exception.code,403);e.exception.close()
        with self.assertRaises(HTTPError) as e:
            self.post(other,otcsrf,self.a,"/settings",{"name":"اختراق"})
        self.assertEqual(e.exception.code,403);e.exception.close()

    def test_repeat_scan_and_report_are_idempotent(self):
        """Double-click does not create duplicate manual scans or Word files."""
        previous=self.app.store.list_scans(self.a)[0]
        sid,created=self.app.store.start_scan(self.a)
        self.assertEqual(sid,previous["id"])
        self.assertFalse(created)
        old=self.app.store.report(self.a,self.report["id"])
        same=self.app.store.create_report(self.a,[self.art["id"]],
                                          old["window_start"],old["window_end"])
        self.assertEqual(same["id"],old["id"])
        self.assertEqual(len(self.app.store.list_reports(self.a)),1)

    def test_restart_new_app_reads_same_archived_word(self):
        old=Path(self.report["file_path"]).read_bytes()
        new_app=App(self.tmp.name,live_only=True)
        got=new_app.store.report(self.a,self.report["id"])
        self.assertEqual(old,Path(got["file_path"]).read_bytes())
        self.assertEqual(got["file_sha"],hashlib.sha256(old).hexdigest())
        token,csrf=new_app.store.login("owner@private.test","owner-private-pass-2026")
        self.assertIsNotNone(new_app.store.session_user(token,csrf))

if __name__=="__main__":
    unittest.main()
