"""Local-only HTTP app: explicit manual actions, per-route tenant ACL.

Never imports scheduled_rasd, SMTP, delivery_bridge or production secrets.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import io
import json
import mimetypes
import os
import secrets
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from .core import ROOT, SOURCE_CATALOG, Store, STATES, utcnow

WEB = Path(__file__).resolve().parent / "static"
MAX_JSON = 220_000


class App:
    def __init__(self, storage: str | Path):
        self.store = Store(storage)

    def handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "RASD-Manual/0.1"

            def log_message(self, format, *args):
                # No cookies, authorization tokens or user input in server logs.
                print("RASD_WEB_STATUS", self.command, self.path.split("?")[0], args[1] if len(args)>1 else "")

            def response(self, status, body=b"", mime="application/json; charset=utf-8", headers=None):
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                 "base-uri 'none'; object-src 'none'; frame-ancestors 'none'")
                for name, value in (headers or {}).items():
                    self.send_header(name,value)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def j(self, status, value, headers=None):
                self.response(status, json.dumps(value, ensure_ascii=False, default=str).encode(),headers=headers)

            def input(self):
                length = int(self.headers.get("Content-Length","0"))
                if length < 1 or length > MAX_JSON:
                    raise ValueError("invalid_json_length")
                raw=self.rfile.read(length)
                val=json.loads(raw)
                if not isinstance(val,dict):
                    raise ValueError("json_object_required")
                return val

            def cookie_token(self):
                cookie=SimpleCookie()
                try:
                    cookie.load(self.headers.get("Cookie",""))
                    return cookie["rasd_sid"].value if "rasd_sid" in cookie else ""
                except Exception:
                    return ""

            def user(self, mutate=False):
                token=self.cookie_token()
                csrf=self.headers.get("X-RASD-CSRF") if mutate else None
                if mutate and not csrf:
                    raise PermissionError("csrf_missing")
                user=app.store.session_user(token,csrf)
                if not user:
                    raise PermissionError("login_required_or_csrf")
                return user

            def guard(self, tenant, required="reader", mutate=False):
                user=self.user(mutate)
                role=app.store.role(user,tenant,required)
                return user,role

            def assets(self, path):
                assets={"/":("index.html","text/html; charset=utf-8"),
                        "/assets/app.js":("app.js","text/javascript; charset=utf-8"),
                        "/assets/style.css":("style.css","text/css; charset=utf-8")}
                if path not in assets:
                    return False
                name,mime=assets[path]
                self.response(200,(WEB/name).read_bytes(),mime)
                return True

            def do_GET(self):
                try:
                    url=urlsplit(self.path)
                    path=url.path
                    if self.assets(path):
                        return
                    parts=[x for x in path.strip("/").split("/") if x]
                    if not parts or parts[0]!="api":
                        return self.j(404,{"error":"not_found"})
                    if parts==["api","health"]:
                        return self.j(200,{"service":"RASD Manual","scheduler":"DISABLED_IN_THIS_APP",
                                           "email":"NOT_IMPLEMENTED","time":utcnow()})
                    user=self.user()
                    if parts==["api","me"]:
                        return self.j(200,{"email":user["email"],"id":user["id"],
                                           "owner":bool(user["platform_owner"]),
                                           "tenants":app.store.memberships(user)})
                    if parts==["api","catalog"]:
                        return self.j(200,{"sources":[{"name":n,"url":u} for n,u in SOURCE_CATALOG],
                                           "demo":["demo://university","demo://foods","demo://unavailable"]})
                    if parts==["api","tenants"]:
                        return self.j(200,{"tenants":app.store.memberships(user)})
                    if len(parts) < 3 or parts[:2]!=["api","tenants"]:
                        return self.j(404,{"error":"not_found"})
                    tid=parts[2]
                    self.guard(tid)
                    if len(parts)==3:
                        tenant=app.store.tenant(tid)
                        tenant["role"]=app.store.role(user,tid)
                        return self.j(200,tenant)
                    action=parts[3]
                    if action=="sources" and len(parts)==4:
                        return self.j(200,{"sources":app.store.sources(tid)})
                    if action=="scans":
                        if len(parts)==4:
                            return self.j(200,{"scans":app.store.list_scans(tid)})
                        if len(parts)==5:
                            scan_id=parts[4]
                            found=next((s for s in app.store.list_scans(tid,200) if s["id"]==scan_id),None)
                            if not found:
                                raise LookupError("scan_not_found")
                            found["source_checks"]=app.store.source_checks(tid,scan_id)
                            return self.j(200,found)
                    if action=="dashboard":
                        articles=app.store.articles(tid)
                        scans=app.store.list_scans(tid,1)
                        reports=app.store.list_reports(tid)
                        pub={}
                        daily={}
                        for article in articles:
                            pub[article["publisher"]]=pub.get(article["publisher"],0)+1
                            date=article["published_at"][:10]
                            daily[date]=daily.get(date,0)+1
                        failed=0
                        if scans:
                            for c in app.store.source_checks(tid,scans[0]["id"]):
                                failed += c["status"]!="ok"
                        return self.j(200,{"last_scan":scans[0] if scans else None,
                            "last_report":reports[0] if reports else None,
                            "sources_unavailable":failed,
                            "news_approved":sum(a["state"]=="approved" for a in articles),
                            "news_pending":sum(a["state"]=="pending" for a in articles),
                            "coverages":len(articles),
                            "events":len({a["event_key"] for a in articles}),
                            "publishers":pub,"timeline":daily,
                            "scheduler":"متوقفة بقرار المالك — التطبيق يدوي بالكامل"})
                    if action=="articles":
                        if len(parts)==4:
                            params=parse_qs(url.query)
                            state=params.get("state",[None])[0]
                            q=params.get("q",[None])[0]
                            publisher=params.get("publisher",[None])[0]
                            since=params.get("since",[None])[0]
                            until=params.get("until",[None])[0]
                            return self.j(200,{"articles":app.store.articles(
                                tid,state=state,query=q,publisher=publisher,since=since,until=until)})
                        if len(parts) in (5,6):
                            art=app.store.article(tid,parts[4])
                            if len(parts)==5:
                                return self.j(200,art)
                            if parts[5]=="image":
                                if not art["image_path"]:
                                    raise LookupError("image_missing")
                                file=app.store.secure_file(tid,art["image_path"])
                                if hashlib.sha256(file.read_bytes()).hexdigest()!=art["image_sha"]:
                                    raise RuntimeError("image_integrity_failed")
                                return self.response(200,file.read_bytes(),"image/jpeg")
                    if action=="reports":
                        if len(parts)==4:
                            return self.j(200,{"reports":app.store.list_reports(tid)})
                        if len(parts)==5:
                            report=app.store.report(tid,parts[4])
                            return self.j(200,report)
                        if len(parts)==6 and parts[5]=="download":
                            report=app.store.report(tid,parts[4])
                            file=app.store.secure_file(tid,report["file_path"])
                            content=file.read_bytes()
                            if not hmac.compare_digest(
                                hashlib.sha256(content).hexdigest(),report["file_sha"]):
                                raise RuntimeError("report_file_integrity_failed")
                            return self.response(200,content,
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                {"Content-Disposition":'attachment; filename="RASD-'+parts[4]+'.docx"'})
                    if action=="logo" and len(parts)==4:
                        tenant=app.store.tenant(tid)
                        if not tenant["logo_path"]:
                            raise LookupError("logo_missing")
                        file=app.store.secure_file(tid,tenant["logo_path"])
                        return self.response(200,file.read_bytes(),"image/png")
                    return self.j(404,{"error":"not_found"})
                except (PermissionError,ValueError,LookupError,RuntimeError,KeyError,json.JSONDecodeError) as exc:
                    self.fail(exc)

            def do_POST(self):
                try:
                    parts=[x for x in urlsplit(self.path).path.strip("/").split("/") if x]
                    if parts==["api","login"]:
                        data=self.input()
                        token,csrf=app.store.login(data.get("email",""),data.get("password",""))
                        secure="; Secure" if self.headers.get("X-Forwarded-Proto")=="https" else ""
                        return self.j(200,{"csrf":csrf},
                           {"Set-Cookie":"rasd_sid="+token+"; Path=/; HttpOnly; SameSite=Strict"+secure,
                            "X-RASD-CSRF-Token":csrf})
                    user=self.user(mutate=True)
                    if parts==["api","logout"]:
                        app.store.logout(self.cookie_token())
                        return self.j(200,{"ok":True},
                                      {"Set-Cookie":"rasd_sid=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"})
                    data=self.input()
                    if parts==["api","tenants"]:
                        if not user["platform_owner"]:
                            raise PermissionError("platform_owner_only")
                        tid=app.store.create_tenant(data.get("name",""),topics=data.get("topics",[]),
                            includes=data.get("includes",[]),excludes=data.get("excludes",[]),
                            timezone_name=data.get("timezone","Africa/Cairo"),
                            language=data.get("language","ar"),
                            target=data.get("target",10),
                            duplicate_policy=data.get("duplicate_policy","events"),
                            template=data.get("template","professional"))
                        return self.j(201,{"id":tid})
                    if len(parts)<4 or parts[:2]!=["api","tenants"]:
                        return self.j(404,{"error":"not_found"})
                    tid,action=parts[2],parts[3]
                    if action=="settings" and len(parts)==4:
                        self.guard(tid,"tenant_admin",True)
                        allowed={"name","topics","includes","excludes","timezone","language",
                                 "target","duplicate_policy","template"}
                        app.store.update_tenant(tid,{k:v for k,v in data.items() if k in allowed})
                        return self.j(200,{"saved":True,"effective_from":"next_manual_scan"})
                    if action=="sources" and len(parts)==4:
                        self.guard(tid,"tenant_admin",True)
                        app.store.add_source(tid,data.get("name",""),data.get("feed_url",""))
                        return self.j(201,{"created":True})
                    if action=="members" and len(parts)==4:
                        self.guard(tid,"tenant_admin",True)
                        uid=app.store.add_member(tid,data.get("email",""),data.get("password",""),
                                                 data.get("role","reader"))
                        return self.j(201,{"id":uid})
                    if action=="scan" and len(parts)==4:
                        self.guard(tid,"analyst",True)
                        sid,new=app.store.start_scan(tid)
                        if new:
                            app.store.run_scan_background(tid,sid)
                        return self.j(202,{"scan_id":sid,"new_scan":new,"duplicate_click":not new})
                    if action=="articles" and len(parts)==6 and parts[5]=="review":
                        self.guard(tid,"analyst",True)
                        app.store.review(tid,parts[4],user["email"],data.get("state",""),
                                         data.get("event_key"))
                        return self.j(200,{"saved":True})
                    if action=="reports" and len(parts)==4:
                        self.guard(tid,"analyst",True)
                        report=app.store.create_report(tid,data.get("article_ids",[]),
                                        data.get("start",""),data.get("end",""))
                        return self.j(201,{"report_id":report["id"],"sha256":report["file_sha"],
                                           "items":len(json.loads(report["manifest"]))})
                    if action=="logo" and len(parts)==4:
                        self.guard(tid,"tenant_admin",True)
                        payload=data.get("data","")
                        if not isinstance(payload,str) or len(payload)>200000:
                            raise ValueError("logo_too_large")
                        raw=base64.b64decode(payload,validate=True)
                        if len(raw)>150000: raise ValueError("logo_too_large")
                        image=Image.open(io.BytesIO(raw))
                        image.verify()
                        image=Image.open(io.BytesIO(raw)).convert("RGBA")
                        if image.width>2000 or image.height>2000:
                            raise ValueError("logo_dimensions_invalid")
                        out=app.store.files/tid/"logo.png"
                        out.parent.mkdir(parents=True,exist_ok=True)
                        image.thumbnail((500,500))
                        image.save(out,"PNG")
                        with app.store.connect() as con:
                            con.execute("UPDATE tenants SET logo_path=? WHERE id=?",(str(out),tid))
                        return self.j(200,{"saved":True})
                    return self.j(404,{"error":"not_found"})
                except (PermissionError,ValueError,LookupError,RuntimeError,KeyError,json.JSONDecodeError,base64.binascii.Error) as exc:
                    self.fail(exc)

            def fail(self,exc):
                if isinstance(exc,PermissionError):
                    status=403
                elif isinstance(exc,LookupError):
                    status=404
                elif isinstance(exc,RuntimeError):
                    status=409
                else:
                    status=400
                self.j(status,{"error":str(exc)[:160]})
        return Handler


def main():
    parser=argparse.ArgumentParser(description="RASD manual multi-tenant local app — NO SEND")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--data",default=str(ROOT/".rasd-manual"))
    parser.add_argument("--seed-demo",action="store_true")
    parser.add_argument("--owner-email",default="owner@rasd.demo")
    parser.add_argument("--owner-password",default=None)
    args=parser.parse_args()
    if args.host not in ("127.0.0.1","localhost","::1"):
        parser.error("MVP refuses publicly exposed HTTP: use a TLS/authenticated deployment after security review")
    app=App(args.data)
    if args.seed_demo:
        info=app.store.seed_demo(args.owner_email,args.owner_password)
        if info:
            print("RASD_DEMO_OWNER_EMAIL="+info["owner_email"],flush=True)
            print("RASD_DEMO_OWNER_PASSWORD="+info["owner_password"],flush=True)
        else:
            print("RASD_DEMO_EXISTS: existing owner password was not reset",flush=True)
    server=ThreadingHTTPServer((args.host,args.port),app.handler())
    print("RASD_LOCAL_MANUAL_URL=http://"+args.host+":"+str(args.port),flush=True)
    print("RASD_SEND=DISABLED RASD_SCHEDULE=DISABLED RASD_PRIVATE_LEDGER=UNTOUCHED",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__=="__main__":
    main()
