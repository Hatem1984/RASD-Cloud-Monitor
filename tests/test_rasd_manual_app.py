"""End-to-end server/store tests for RASD manual tenant demo, offline NO SEND."""
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

from docx import Document
from PIL import Image

from rasd_app.core import Store, DEMO_FEEDS
from rasd_app.server import App


class DemoJourney(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=Store(self.tmp.name)
        self.owner=self.store.create_user("owner@example.test","correct-horse-battery-stage",owner=True)
        self.uni=self.store.create_tenant("جامعة الأفق التجريبية",topics=["التعليم"],
                includes=["الجامعات","طلاب","البحث"],duplicate_policy="coverages",target=10)
        self.food=self.store.create_tenant("مصنع الغذاء التجريبي",topics=["الأغذية"],
                includes=["الأغذية","الغذائي"],duplicate_policy="coverages",target=10)
        self.empty=self.store.create_tenant("جهة بلا بيانات",includes=["لا يوجد"])
        self.store.add_source(self.uni,"مصدر تعليم Demo","demo://university")
        self.store.add_source(self.uni,"مصدر متعذر Demo","demo://unavailable")
        self.store.add_source(self.food,"مصدر غذائي Demo","demo://foods")

    def run_scan(self,tid):
        scan,created=self.store.start_scan(tid)
        self.assertTrue(created)
        self.store.run_scan(tid,scan)
        return self.store.list_scans(tid)[0]

    def approved(self,tid):
        records=self.store.articles(tid)
        for a in records:
            self.store.review(tid,a["id"],"analyst@demo.test","approved")
        return [x["id"] for x in records]

    def test_manual_two_tenants_and_source_partial_failure(self):
        un=self.run_scan(self.uni)
        food=self.run_scan(self.food)
        a=json.loads(un["summary"])
        self.assertEqual(un["status"],"partial")
        self.assertEqual(a["sources_ok"],1)
        self.assertEqual(a["sources_unavailable"],1)
        self.assertEqual(a["new_matching_coverages"],4)
        self.assertEqual(food["status"],"complete")
        self.assertEqual(json.loads(food["summary"])["new_matching_coverages"],3)
        self.assertEqual(len(self.store.articles(self.uni)),4)
        self.assertEqual(len(self.store.articles(self.food)),3)
        self.assertTrue(all("university" in x["url"] for x in self.store.articles(self.uni)))
        self.assertTrue(all("foods" in x["url"] for x in self.store.articles(self.food)))
        checks=self.store.source_checks(self.uni,un["id"])
        self.assertEqual(len(checks),2)
        self.assertEqual({x["status"] for x in checks},{"ok","unavailable"})
        self.assertIn("demo_source_unavailable",{x["reason"] for x in checks})

    def test_double_click_does_not_create_two_scans(self):
        sid,first=self.store.start_scan(self.uni)
        second,created=self.store.start_scan(self.uni)
        self.assertEqual(sid,second)
        self.assertTrue(first)
        self.assertFalse(created)
        self.store.run_scan(self.uni,sid)
        third,created=self.store.start_scan(self.uni)
        self.assertEqual(sid,third)
        self.assertFalse(created)
        self.assertEqual(len(self.store.list_scans(self.uni)),1)

    def test_zero_result_is_explicit_and_word_still_works(self):
        empty=self.run_scan(self.empty)
        self.assertEqual(empty["status"],"complete")
        self.assertEqual(json.loads(empty["summary"])["new_matching_coverages"],0)
        report=self.store.create_report(self.empty,[],
                   "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        self.assertEqual(json.loads(report["manifest"]),[])
        self.assertTrue(Path(report["file_path"]).is_file())
        self.assertIn("رصد", "\n".join(p.text for p in Document(report["file_path"]).paragraphs))

    def test_word_preserves_exact_order_links_and_image_sha(self):
        self.run_scan(self.uni)
        ids=self.approved(self.uni)
        report=self.store.create_report(self.uni,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        manifest=json.loads(report["manifest"])
        self.assertEqual([x["id"] for x in manifest],ids)
        doc=Document(report["file_path"])
        self.assertEqual(len(doc.inline_shapes),len(manifest))
        self.assertEqual([x["url"] for x in manifest],
            [doc.part.rels[link.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")].target_ref
             for link in doc.element.body.xpath(".//w:hyperlink")])
        image_shas=[hashlib.sha256(doc.part.related_parts[
                im.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")].blob).hexdigest()
                for im in doc.element.body.xpath(".//a:blip")]
        self.assertEqual(image_shas,[m["image_sha"] for m in manifest])
        self.assertTrue(all(x["image_state"]=="demo_illustration" for x in manifest))
        self.assertEqual(report["file_sha"],hashlib.sha256(Path(report["file_path"]).read_bytes()).hexdigest())
        again=self.store.create_report(self.uni,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        self.assertEqual(report["id"],again["id"])
        self.assertEqual(len(self.store.list_reports(self.uni)),1)
        self.assertEqual([a["event_key"] for a in self.store.articles(self.uni)].count("demo-university-training"),3)

    def test_event_policy_one_event_three_coverages(self):
        self.run_scan(self.uni)
        ids=self.approved(self.uni)
        self.store.update_tenant(self.uni,{"duplicate_policy":"events"})
        report=self.store.create_report(self.uni,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        self.assertEqual(len(json.loads(report["manifest"])),2)
        self.assertEqual(len(self.store.articles(self.uni)),4)

    def test_immutable_old_report_after_brand_change(self):
        self.run_scan(self.food)
        ids=self.approved(self.food)
        one=self.store.create_report(self.food,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        before=Path(one["file_path"]).read_bytes()
        self.store.update_tenant(self.food,{"name":"قطاع الغذاء — اسم جديد","target":3})
        two=self.store.create_report(self.food,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        self.assertNotEqual(one["id"],two["id"])
        self.assertEqual(before,Path(one["file_path"]).read_bytes())
        self.assertIn("مصنع الغذاء",json.loads(one["settings"])["name"])

    def test_logo_replacement_creates_new_immutable_branded_word(self):
        self.run_scan(self.food)
        ids=self.approved(self.food)
        logo=self.store.files/self.food/"logo.png"
        logo.parent.mkdir(parents=True,exist_ok=True)
        Image.new("RGB",(250,110),"navy").save(logo,"PNG")
        with self.store.connect() as con:
            con.execute("UPDATE tenants SET logo_path=? WHERE id=?",(str(logo),self.food))
        one=self.store.create_report(self.food,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        old_bytes=Path(one["file_path"]).read_bytes()
        first_logo_sha=json.loads(one["settings"])["logo_sha256"]
        self.assertEqual(len(Document(one["file_path"]).inline_shapes),len(ids)+1)
        self.assertEqual(len(Document(one["file_path"]).tables),len(ids))
        for table in Document(one["file_path"]).tables:
            self.assertEqual(len(table.rows[0]._tr.xpath(".//w:cantSplit")),1)
        Image.new("RGB",(250,110),"maroon").save(logo,"PNG")
        two=self.store.create_report(self.food,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        self.assertNotEqual(one["id"],two["id"])
        self.assertNotEqual(first_logo_sha,json.loads(two["settings"])["logo_sha256"])
        self.assertEqual(old_bytes,Path(one["file_path"]).read_bytes())
        self.assertEqual(len(self.store.list_reports(self.food)),2)

    def test_tampered_image_fails_closed_without_report(self):
        self.run_scan(self.food)
        ids=self.approved(self.food)
        item=self.store.article(self.food,ids[0])
        Path(item["image_path"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(RuntimeError,"report_image_integrity_hold"):
            self.store.create_report(self.food,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        self.assertEqual(self.store.list_reports(self.food),[])

    def test_unreviewed_and_bad_timezone_hold(self):
        self.run_scan(self.uni)
        with self.assertRaisesRegex(ValueError,"report_requires_approved_items"):
            self.store.create_report(self.uni,[self.store.articles(self.uni)[0]["id"]],
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError,"invalid_report_window"):
            self.store.create_report(self.uni,[],"2026-11-23","2100-01-01")

    def test_reject_arbitrary_and_internal_feed_urls(self):
        for feed in ("http://127.0.0.1:8765/private","https://127.0.0.1/rss",
                     "https://example.org/news/rss","file:///etc/passwd"):
            with self.subTest(feed=feed),self.assertRaises(ValueError):
                self.store.add_source(self.uni,"source",feed)

    def test_store_roles_and_private_files(self):
        anna=self.store.add_member(self.uni,"anna@example.test","a-large-valid-password","analyst")
        bob=self.store.add_member(self.food,"bob@example.test","another-valid-password","reader")
        with self.store.connect() as con:
            a=dict(con.execute("SELECT * FROM users WHERE id=?",(anna,)).fetchone())
            b=dict(con.execute("SELECT * FROM users WHERE id=?",(bob,)).fetchone())
        self.assertEqual(self.store.role(a,self.uni,"analyst"),"analyst")
        with self.assertRaises(PermissionError):
            self.store.role(a,self.food)
        with self.assertRaises(PermissionError):
            self.store.role(b,self.food,"analyst")
        self.run_scan(self.food)
        ids=self.approved(self.food)
        report=self.store.create_report(self.food,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        with self.assertRaises(PermissionError):
            self.store.secure_file(self.uni,report["file_path"])
        with self.assertRaises(LookupError):
            self.store.report(self.uni,report["id"])


class TenantAPI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        app=App(self.temp.name)
        self.app=app
        self.store=app.store
        a=self.store.create_tenant("جهة ألف",includes=["الجامعات"])
        b=self.store.create_tenant("جهة باء",includes=["الأغذية"])
        self.a,self.b=a,b
        self.store.add_source(a,"demo university","demo://university")
        self.store.add_source(b,"demo foods","demo://foods")
        self.store.add_member(a,"alice@example.test","alice-secret-password","analyst")
        self.store.add_member(b,"bob@example.test","bobs-secret-password","analyst")
        self.server=ThreadingHTTPServer(("127.0.0.1",0),app.handler())
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base="http://127.0.0.1:"+str(self.server.server_port)

    def browser(self,email,password):
        cj=CookieJar()
        opener=build_opener(HTTPCookieProcessor(cj))
        payload=json.dumps({"email":email,"password":password}).encode()
        req=Request(self.base+"/api/login",data=payload,
                    headers={"Content-Type":"application/json"})
        with opener.open(req) as resp:
            csrf=json.loads(resp.read())["csrf"]
        return opener,csrf

    def post(self,opener,csrf,path,payload):
        req=Request(self.base+path,data=json.dumps(payload).encode(),
             headers={"Content-Type":"application/json","X-RASD-CSRF":csrf})
        return opener.open(req)

    def test_cross_tenant_direct_report_link_forbidden(self):
        alice,csrfA=self.browser("alice@example.test","alice-secret-password")
        bob,csrfB=self.browser("bob@example.test","bobs-secret-password")
        self.store.run_scan(self.b,self.store.start_scan(self.b)[0])
        ids=[a["id"] for a in self.store.articles(self.b)]
        for aid in ids:self.store.review(self.b,aid,"bob","approved")
        report=self.store.create_report(self.b,ids,
                         "2000-01-01T00:00:00+00:00","2100-01-01T00:00:00+00:00")
        target="/api/tenants/"+self.b+"/reports/"+report["id"]+"/download"
        with bob.open(self.base+target) as response:
            content=response.read()
            self.assertEqual(response.status,200)
            self.assertEqual(hashlib.sha256(content).hexdigest(),report["file_sha"])
        with self.assertRaises(HTTPError) as exc:
            alice.open(self.base+target)
        self.assertEqual(exc.exception.code,403)
        with self.assertRaises(HTTPError) as exc:
            alice.open(self.base+"/api/tenants/"+self.b+"/articles")
        self.assertEqual(exc.exception.code,403)
        with self.assertRaises(HTTPError) as exc:
            self.post(alice,csrfA,"/api/tenants/"+self.b+"/scan",{})
        self.assertEqual(exc.exception.code,403)

    def test_server_login_csrf_permissions_and_new_tenant(self):
        alice,csrf=self.browser("alice@example.test","alice-secret-password")
        with self.assertRaises(HTTPError) as exc:
            self.post(alice,csrf,"/api/tenants",{"name":"not_owner"})
        self.assertEqual(exc.exception.code,403)
        with self.assertRaises(HTTPError) as exc:
            self.post(alice,"WRONG-CSRF","/api/tenants/"+self.a+"/scan",{})
        self.assertEqual(exc.exception.code,403)
        with self.post(alice,csrf,"/api/tenants/"+self.a+"/scan",{}) as resp:
            self.assertEqual(resp.status,202)
            self.assertIn("scan_id",json.loads(resp.read()))


if __name__=="__main__":
    unittest.main()
