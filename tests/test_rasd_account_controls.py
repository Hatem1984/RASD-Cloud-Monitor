"""Private account self-service, membership disable, session expiry over HTTP."""
import json,unittest
from datetime import datetime,timedelta,timezone
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPCookieProcessor,Request
from test_rasd_enterprise_http_access import RoleHTTPAcceptance,payload


class TestAccountControls(unittest.TestCase):
    login=RoleHTTPAcceptance.login
    get=RoleHTTPAcceptance.get
    post=RoleHTTPAcceptance.post

    def setUp(self):
        RoleHTTPAcceptance.setUp(self)
        self.store=self.app.store

    def test_disabled_user_loses_direct_image_and_report_access(self):
        admin,csrf=self.login("admin-a@private.test","admin-a-private-pass")
        reader,reader_csrf=self.login("reader-a@private.test","reader-a-private-pass")
        members=self.store.tenant_members(self.a)
        uid=next(x["id"] for x in members if x["email"]=="reader-a@private.test")
        old=self.report["id"]
        # Before disable, this user can read article and download Word.
        with self.get(reader,self.a,"/articles/"+self.art["id"]) as r:self.assertEqual(r.status,200)
        with self.get(reader,self.a,"/reports/"+old+"/download") as r:self.assertEqual(r.status,200)
        with self.post(admin,csrf,self.a,"/members/"+uid+"/status",{"enabled":False}) as r:
            self.assertFalse(json.loads(r.read())["enabled"])
        for target in ("/articles","/articles/"+self.art["id"]+"/image","/reports",
                       "/reports/"+old+"/download","/dashboard"):
            with self.subTest(url=target),self.assertRaises(HTTPError) as e:
                self.get(reader,self.a,target)
            self.assertEqual(e.exception.code,403)
            e.exception.close()
        with self.assertRaises(HTTPError) as e:
            self.post(reader,reader_csrf,self.a,"/articles/"+self.art["id"]+"/review",
                      {"state":"approved"})
        self.assertEqual(e.exception.code,403);e.exception.close()
        # After reactivation, a fresh login is required because disabling
        # deleted the old session token, not just hidden the UI controls.
        self.post(admin,csrf,self.a,"/members/"+uid+"/status",{"enabled":True}).close()
        with self.assertRaises(HTTPError):
            self.get(reader,self.a,"/reports")
        fresh,_=self.login("reader-a@private.test","reader-a-private-pass")
        with self.get(fresh,self.a,"/reports") as r:self.assertEqual(r.status,200)

    def test_change_password_revokes_existing_sessions(self):
        reader,csrf=self.login("reader-a@private.test","reader-a-private-pass")
        new="new-customer-long-credential-2026"
        with reader.open(Request(self.base+"/api/account/password",
                data=payload({"current_password":"reader-a-private-pass",
                              "new_password":new}),
                headers={"Content-Type":"application/json","X-RASD-CSRF":csrf})) as r:
            self.assertTrue(json.loads(r.read())["session_revoked"])
        with self.assertRaises(HTTPError) as e:self.get(reader,self.a,"/reports")
        self.assertEqual(e.exception.code,403);e.exception.close()
        with self.assertRaises(HTTPError):
            self.login("reader-a@private.test","reader-a-private-pass")
        fresh,_=self.login("reader-a@private.test",new)
        with self.get(fresh,self.a,"/reports") as r:self.assertEqual(r.status,200)

    def test_expired_session_denies_direct_download(self):
        reader,csrf=self.login("reader-a@private.test","reader-a-private-pass")
        with self.store.connect() as db:
            db.execute("UPDATE sessions SET expires_at=? WHERE user_id=(SELECT id FROM users WHERE email=?)",
                ((datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat(),"reader-a@private.test"))
        with self.assertRaises(HTTPError) as e:
            self.get(reader,self.a,"/reports/"+self.report["id"]+"/download")
        self.assertEqual(e.exception.code,403);e.exception.close()

    def test_cannot_disable_self_or_other_tenant_member(self):
        admin,csrf=self.login("admin-a@private.test","admin-a-private-pass")
        uid=next(x["id"] for x in self.store.tenant_members(self.a)
                 if x["email"]=="admin-a@private.test")
        with self.assertRaises(HTTPError) as e:
            self.post(admin,csrf,self.a,"/members/"+uid+"/status",{"enabled":False})
        self.assertEqual(e.exception.code,400);e.exception.close()
        stranger=next(x["id"] for x in self.store.tenant_members(self.b)
                      if x["email"]=="admin-b@private.test")
        with self.assertRaises(HTTPError) as e:
            self.post(admin,csrf,self.a,"/members/"+stranger+"/status",{"enabled":False})
        self.assertEqual(e.exception.code,404);e.exception.close()

    def test_scan_metrics_link_to_exact_tenant_articles(self):
        reader,_=self.login("reader-a@private.test","reader-a-private-pass")
        sid=self.store.list_scans(self.a)[0]["id"]
        with self.get(reader,self.a,"/scans/"+sid) as r:
            result=json.loads(r.read())["metrics"]
        self.assertEqual(result["coverages"],1)
        self.assertEqual(result["events"],1)
        self.assertEqual(result["approved"],1)
        self.assertEqual(result["report_selected"],1)
        for query in ("scan_id="+sid,"scan_id="+sid+"&state=approved",
                      "scan_id="+sid+"&reported=yes"):
            with self.get(reader,self.a,"/articles?"+query) as r:
                self.assertEqual([a["id"] for a in json.loads(r.read())["articles"]],[self.art["id"]])
        with self.get(reader,self.a,"/articles?scan_id="+sid+"&image_state=verified_original") as r:
            self.assertEqual(json.loads(r.read())["articles"],[])
        with self.assertRaises(HTTPError) as e:
            self.get(reader,self.b,"/scans/"+sid)
        self.assertEqual(e.exception.code,403);e.exception.close()

if __name__=="__main__":unittest.main()
