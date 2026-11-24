"""Isolated local multi-tenant manual monitoring. NO mail, cron, or private CAS.

Only demo:// feeds are synthetic. Live RSS uses the upstream reviewed exact
publisher endpoints. Unknown URLs are rejected, not fetched.
"""
from __future__ import annotations

import hashlib
import hmac
from contextlib import contextmanager
import io
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc
ROLES = {"tenant_admin", "analyst", "reader"}
STATES = {"pending", "approved", "rejected"}
DEMO_FEEDS = {"demo://university", "demo://foods", "demo://unavailable"}
SOURCE_CATALOG = (
    ("الشروق – اقتصاد", "https://www.shorouknews.com/Economy/rss"),
    ("حابي", "https://hapijournal.com/feed/"),
    ("المصري اليوم", "https://www.almasryalyoum.com/rss/rssfeeds"),
    ("البورصة", "https://alborsaanews.com/category/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%89/feed"),
    ("النهار", "https://www.alnaharegypt.com/feed/"),
)
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL,
 password_hash TEXT NOT NULL, platform_owner INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS tenants(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'Africa/Cairo',
 language TEXT NOT NULL DEFAULT 'ar', topics TEXT NOT NULL DEFAULT '[]',
 includes TEXT NOT NULL DEFAULT '[]', excludes TEXT NOT NULL DEFAULT '[]',
 template TEXT NOT NULL DEFAULT 'professional', target INTEGER NOT NULL DEFAULT 10,
 duplicate_policy TEXT NOT NULL DEFAULT 'events', logo_path TEXT,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memberships(
 user_id TEXT NOT NULL REFERENCES users(id), tenant_id TEXT NOT NULL REFERENCES tenants(id),
 role TEXT NOT NULL CHECK(role IN ('tenant_admin','analyst','reader')),
 PRIMARY KEY(user_id, tenant_id));
CREATE TABLE IF NOT EXISTS sources(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 name TEXT NOT NULL, feed_url TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 last_ok TEXT, last_error TEXT, checked INTEGER NOT NULL DEFAULT 0,
 qualified INTEGER NOT NULL DEFAULT 0, UNIQUE(tenant_id,feed_url));
CREATE TABLE IF NOT EXISTS scans(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 status TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
 summary TEXT NOT NULL DEFAULT '{}');
CREATE UNIQUE INDEX IF NOT EXISTS one_running_scan_per_tenant
 ON scans(tenant_id) WHERE status='running';
CREATE TABLE IF NOT EXISTS source_checks(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 scan_id TEXT NOT NULL REFERENCES scans(id), source_id TEXT NOT NULL REFERENCES sources(id),
 status TEXT NOT NULL, scanned INTEGER NOT NULL DEFAULT 0,
 matched INTEGER NOT NULL DEFAULT 0, reason TEXT);
CREATE TABLE IF NOT EXISTS articles(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 source_id TEXT NOT NULL REFERENCES sources(id), scan_id TEXT NOT NULL REFERENCES scans(id),
 title TEXT NOT NULL, publisher TEXT NOT NULL, url TEXT NOT NULL,
 published_at TEXT NOT NULL, discovered_at TEXT NOT NULL, match_reason TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending', event_key TEXT NOT NULL,
 image_path TEXT, image_sha TEXT, image_state TEXT NOT NULL DEFAULT 'missing',
 demo INTEGER NOT NULL DEFAULT 0, review_log TEXT NOT NULL DEFAULT '[]',
 UNIQUE(tenant_id,url));
CREATE INDEX IF NOT EXISTS tenant_article_idx ON articles(tenant_id,published_at);
CREATE TABLE IF NOT EXISTS reports(
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 created_at TEXT NOT NULL, window_start TEXT NOT NULL, window_end TEXT NOT NULL,
 file_path TEXT NOT NULL, file_sha TEXT NOT NULL,
 manifest TEXT NOT NULL, settings TEXT NOT NULL, request_key TEXT NOT NULL,
 UNIQUE(tenant_id,request_key));
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 csrf_hash TEXT NOT NULL, expires_at TEXT NOT NULL);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id() -> str:
    return secrets.token_hex(12)


def clean_terms(value) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,،\n]", value)
    if not isinstance(value, list):
        raise ValueError("invalid_terms")
    terms = [str(x).strip() for x in value if str(x).strip()]
    if len(terms) > 50 or any(len(x) > 100 for x in terms):
        raise ValueError("terms_limit_exceeded")
    return list(dict.fromkeys(terms))


def validate_feed(url: str) -> str:
    from monitor import APPROVED_FEED_URLS
    if url in DEMO_FEEDS or url in APPROVED_FEED_URLS:
        return url
    raise ValueError("source_not_reviewed_choose_catalog")


def digest_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               bytes.fromhex(salt), 250_000).hex()


def event_key(title: str) -> str:
    simplified = re.sub(r"[\W_]+", " ", title.casefold(), flags=re.UNICODE).strip()
    return hashlib.sha256(simplified.encode()).hexdigest()[:20]


def demo_items(feed: str) -> list[dict]:
    if feed == "demo://unavailable":
        raise RuntimeError("demo_source_unavailable")
    if feed == "demo://university":
        return [
            {"title": "الجامعات تعلن برنامجًا جديدًا للتدريب البحثي", "publisher": p,
             "url": "https://example.org/rasd-demo/university/" + str(i),
             "published": "2026-11-23T08:10:00+02:00",
             "event": "demo-university-training"} for i, p in enumerate(
                 ("صحيفة الجامعة التجريبية", "مجلة التعليم التجريبية", "وكالة الطلاب التجريبية"), 1)
        ] + [
            {"title": "إطلاق مسابقة طلابية للبحث العلمي", "publisher": "الموقع الجامعي التجريبي",
             "url": "https://example.org/rasd-demo/university/4",
             "published": "2026-11-23T09:00:00+02:00",
             "event": "demo-university-contest"}]
    if feed == "demo://foods":
        return [
            {"title": "قطاع الأغذية يناقش معايير سلامة الإنتاج", "publisher": p,
             "url": "https://example.org/rasd-demo/foods/" + str(i),
             "published": "2026-11-23T09:40:00+02:00", "event": "demo-food-safety"}
            for i, p in enumerate(("نشرة الأغذية التجريبية", "بوابة الصناعة التجريبية"), 1)
        ] + [{"title": "دراسة افتراضية عن سلاسل الإمداد الغذائي",
              "publisher": "مجلة السوق التجريبية",
              "url": "https://example.org/rasd-demo/foods/3",
              "published": "2026-11-23T07:20:00+02:00", "event": "demo-food-supply"}]
    raise ValueError("unknown_demo_source")


def parse_live_feed(url: str) -> list[dict]:
    from monitor import read_feed, APPROVED_FEED_URLS
    if url not in APPROVED_FEED_URLS:
        raise ValueError("source_not_reviewed")
    data = read_feed(url, 800_000)
    root = ET.fromstring(data)
    entries = root.findall("./channel/item")
    if not entries:
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    feed_host = urlsplit(url).hostname or ""
    results = []
    for entry in entries[:100]:
        title = (entry.findtext("title") or entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        if not link:
            atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
            link = "" if atom_link is None else atom_link.attrib.get("href", "")
        parsed = urlsplit(link)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            continue
        host = parsed.hostname
        # A publisher may distribute RSS on a subdomain of the article domain.
        base = feed_host.removeprefix("www.")
        if not (host == base or host.endswith("." + base) or
                base.endswith("." + host.removeprefix("www."))):
            continue
        published = (entry.findtext("pubDate") or entry.findtext("{http://purl.org/dc/elements/1.1/}date")
                     or entry.findtext("{http://www.w3.org/2005/Atom}published") or "")
        try:
            stamp = parsedate_to_datetime(published)
            if stamp.tzinfo is None:
                raise ValueError("naive_date")
            published = stamp.astimezone(UTC).isoformat()
        except (ValueError, TypeError):
            try:
                stamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("naive_date")
                published = stamp.astimezone(UTC).isoformat()
            except ValueError:
                continue
        if not title or len(title) > 600 or not link:
            continue
        results.append({"title": title, "publisher": feed_host,
                        "url": link, "published": published,
                        "event": event_key(title)})
    return results


def make_demo_image(path: Path, title: str, publisher: str) -> str:
    """Explicitly fake fixture. Never label an illustrative image as original."""
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1200, 740), "#e7e9f0")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1200, 116), fill="#152740")
    d.rectangle((0, 116, 1200, 128), fill="#c4a56b")
    d.rounded_rectangle((75, 185, 1125, 590), radius=22, fill="#ffffff")
    d.text((105, 42), "RASD    /    DEMO ONLY", fill="white")
    d.text((125, 252), "ILLUSTRATIVE IMAGE - NOT A PUBLISHER SCREENSHOT", fill="#243b53")
    d.text((125, 335), hashlib.sha256((title + publisher).encode()).hexdigest()[:28],
           fill="#43516e")
    d.text((125, 475), "Source evidence: NOT VERIFIED", fill="#a03d42")
    im.save(path, format="JPEG", quality=87)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Store:
    def __init__(self, base: str | Path):
        self.base = Path(base).resolve()
        self.base.mkdir(parents=True, exist_ok=True)
        self.db = self.base / "rasd_demo.sqlite"
        self.files = self.base / "private_files"
        self.files.mkdir(exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=15000")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def create_user(self, email: str, password: str, *, owner=False) -> str:
        email = email.strip().lower()
        if not email or len(password) < 12 or len(password) > 256:
            raise ValueError("invalid_user_or_password")
        uid, salt = new_id(), secrets.token_hex(16)
        with self.connect() as con:
            con.execute("INSERT INTO users(id,email,salt,password_hash,platform_owner) VALUES(?,?,?,?,?)",
                        (uid, email, salt, digest_password(password, salt), int(owner)))
        return uid

    def login(self, email: str, password: str):
        with self.connect() as con:
            u = con.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
            if not u or not hmac.compare_digest(u["password_hash"], digest_password(password, u["salt"])):
                raise PermissionError("invalid_credentials")
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            expiry = datetime.now(UTC).timestamp() + 8 * 3600
            con.execute("INSERT INTO sessions VALUES(?,?,?,?)",
                        (hashlib.sha256(token.encode()).hexdigest(), u["id"],
                         hashlib.sha256(csrf.encode()).hexdigest(),
                         datetime.fromtimestamp(expiry, UTC).isoformat()))
        return token, csrf

    def session_user(self, token: str, csrf: str | None = None):
        if not token:
            return None
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as con:
            row = con.execute("""SELECT u.*,s.csrf_hash,s.expires_at FROM sessions s
                                 JOIN users u ON u.id=s.user_id WHERE s.token_hash=?""",
                              (key,)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
            return None
        if csrf is not None and not hmac.compare_digest(
                row["csrf_hash"], hashlib.sha256(csrf.encode()).hexdigest()):
            return None
        return dict(row)

    def logout(self, token: str):
        with self.connect() as con:
            con.execute("DELETE FROM sessions WHERE token_hash=?",
                        (hashlib.sha256(token.encode()).hexdigest(),))

    def memberships(self, user: dict):
        with self.connect() as con:
            if user["platform_owner"]:
                rows = con.execute("SELECT t.*, 'tenant_admin' AS role FROM tenants t ORDER BY name").fetchall()
            else:
                rows = con.execute("""SELECT t.*,m.role FROM tenants t
                    JOIN memberships m ON m.tenant_id=t.id
                    WHERE m.user_id=? ORDER BY t.name""", (user["id"],)).fetchall()
        return [dict(r) for r in rows]

    def role(self, user: dict, tenant: str, required: str = "reader"):
        if user.get("platform_owner"):
            return "platform_owner"
        with self.connect() as con:
            row = con.execute("SELECT role FROM memberships WHERE user_id=? AND tenant_id=?",
                              (user["id"], tenant)).fetchone()
        rank = {"reader": 1, "analyst": 2, "tenant_admin": 3}
        if not row or rank[row["role"]] < rank[required]:
            raise PermissionError("tenant_access_denied")
        return row["role"]

    def tenant(self, tid: str) -> dict:
        with self.connect() as con:
            row = con.execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
        if not row:
            raise LookupError("tenant_not_found")
        data = dict(row)
        for field in ("topics", "includes", "excludes"):
            data[field] = json.loads(data[field])
        return data

    def create_tenant(self, name: str, *, topics=None, includes=None, excludes=None,
                      target=10, timezone_name="Africa/Cairo", language="ar",
                      template="professional", duplicate_policy="events") -> str:
        name = str(name).strip()
        if not 2 <= len(name) <= 150:
            raise ValueError("tenant_name_invalid")
        if not isinstance(target, int) or not 1 <= target <= 360:
            raise ValueError("tenant_target_invalid")
        ZoneInfo(timezone_name)
        if language not in ("ar", "en") or template not in ("professional", "brief") or duplicate_policy not in ("events", "coverages"):
            raise ValueError("invalid_tenant_settings")
        tid = new_id()
        with self.connect() as con:
            con.execute("INSERT INTO tenants VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (tid, name, timezone_name, language,
                         json.dumps(clean_terms(topics or []), ensure_ascii=False),
                         json.dumps(clean_terms(includes or []), ensure_ascii=False),
                         json.dumps(clean_terms(excludes or []), ensure_ascii=False),
                         template, target, duplicate_policy, None, utcnow()))
        return tid

    def update_tenant(self, tid: str, values: dict):
        current = self.tenant(tid)
        merged = {**current, **values}
        name = str(merged["name"]).strip()
        if not 2 <= len(name) <= 150:
            raise ValueError("tenant_name_invalid")
        ZoneInfo(merged["timezone"])
        if merged["language"] not in ("ar","en") or merged["template"] not in ("professional","brief"):
            raise ValueError("tenant_settings_invalid")
        if merged["duplicate_policy"] not in ("events","coverages") or type(merged["target"]) is not int or not 1 <= merged["target"] <= 360:
            raise ValueError("tenant_policy_invalid")
        with self.connect() as con:
            con.execute("""UPDATE tenants SET name=?,timezone=?,language=?,topics=?,includes=?,
                       excludes=?,template=?,target=?,duplicate_policy=? WHERE id=?""",
                        (name, merged["timezone"], merged["language"],
                         json.dumps(clean_terms(merged["topics"]),ensure_ascii=False),
                         json.dumps(clean_terms(merged["includes"]),ensure_ascii=False),
                         json.dumps(clean_terms(merged["excludes"]),ensure_ascii=False),
                         merged["template"], merged["target"],merged["duplicate_policy"],tid))

    def add_member(self, tid: str, email: str, password: str, role: str):
        if role not in ROLES:
            raise ValueError("role_invalid")
        with self.connect() as con:
            existing = con.execute("SELECT id FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
        uid = existing["id"] if existing else self.create_user(email, password)
        with self.connect() as con:
            con.execute("INSERT INTO memberships(user_id,tenant_id,role) VALUES(?,?,?)", (uid,tid,role))
        return uid

    def add_source(self, tenant: str, name: str, feed: str):
        validate_feed(feed)
        name = str(name).strip()
        if not name or len(name) > 150:
            raise ValueError("source_name_invalid")
        with self.connect() as con:
            con.execute("INSERT INTO sources(id,tenant_id,name,feed_url) VALUES(?,?,?,?)",
                        (new_id(), tenant, name,feed))

    def toggle_source(self, tid: str, sid: str, enabled: bool):
        if type(enabled) is not bool:
            raise ValueError("invalid_enabled_flag")
        with self.connect() as con:
            result=con.execute("UPDATE sources SET enabled=? WHERE tenant_id=? AND id=?",
                               (int(enabled),tid,sid))
            if result.rowcount!=1:
                raise LookupError("source_not_found_for_tenant")

    def sources(self, tid: str):
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM sources WHERE tenant_id=? ORDER BY name",(tid,))]

    def list_scans(self, tid: str, limit=20):
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM scans WHERE tenant_id=? ORDER BY started_at DESC LIMIT ?", (tid,limit))]

    def start_scan(self, tid: str) -> tuple[str,bool]:
        # Atomic idempotence even under concurrent double-click/retries.
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute(
                "SELECT id,started_at,status FROM scans WHERE tenant_id=? ORDER BY started_at DESC LIMIT 1",
                (tid,)).fetchone()
            if existing and (existing["status"] == "running" or
                    (datetime.now(UTC) - datetime.fromisoformat(
                        existing["started_at"])).total_seconds() < 8):
                return existing["id"], False
            sid = new_id()
            con.execute("INSERT INTO scans(id,tenant_id,status,started_at) VALUES(?,?,?,?)",
                        (sid,tid,"running",utcnow()))
        return sid,True

    def articles(self, tid: str, *, state=None, query=None, publisher=None, since=None, until=None):
        sql = "SELECT * FROM articles WHERE tenant_id=?"
        params=[tid]
        if state in STATES:
            sql += " AND state=?"; params.append(state)
        if query:
            sql += " AND (title LIKE ? OR publisher LIKE ?)"; params.extend(["%"+query+"%"]*2)
        if publisher:
            sql += " AND publisher=?"; params.append(publisher)
        if since:
            sql += " AND published_at>=?"; params.append(since)
        if until:
            sql += " AND published_at<=?"; params.append(until)
        sql += " ORDER BY published_at DESC, id LIMIT 1000"
        with self.connect() as con:
            return [dict(r) for r in con.execute(sql,params)]

    def article(self, tid: str, aid: str) -> dict:
        with self.connect() as con:
            row = con.execute("SELECT * FROM articles WHERE tenant_id=? AND id=?", (tid,aid)).fetchone()
        if not row:
            raise LookupError("article_not_found")
        return dict(row)

    def review(self, tid: str, aid: str, actor: str, state: str, event=None):
        if state not in STATES:
            raise ValueError("review_status_invalid")
        item=self.article(tid,aid)
        history=json.loads(item["review_log"])
        history.append({"by":actor,"state":state,"at":utcnow()})
        ev=str(event).strip()[:100] if event else item["event_key"]
        with self.connect() as con:
            con.execute("""UPDATE articles SET state=?,event_key=?,review_log=?
                          WHERE tenant_id=? AND id=?""",
                        (state,ev,json.dumps(history,ensure_ascii=False),tid,aid))

    def capture_original(self, tid: str, aid: str) -> dict:
        """Optional user-clicked capture; never label a generated image original."""
        article=self.article(tid,aid)
        if article["demo"]:
            return {"ok":False,"reason":"demo_illustration_not_a_publisher_frame"}
        dest=self.files/tid/"images"/(aid+".jpg")
        dest.parent.mkdir(parents=True,exist_ok=True)
        try:
            from .capture import capture_manual_article
            result=capture_manual_article(article,dest)
        except Exception as exc:
            result={"ok":False,"reason":type(exc).__name__}
        if not result.get("ok"):
            return result
        digest=hashlib.sha256(dest.read_bytes()).hexdigest()
        if result.get("sha256")!=digest:
            dest.unlink(missing_ok=True)
            return {"ok":False,"reason":"publisher_frame_digest_mismatch"}
        with self.connect() as con:
            con.execute("""UPDATE articles SET image_path=?,image_sha=?,
                image_state='verified_original' WHERE tenant_id=? AND id=?""",
                (str(dest),digest,tid,aid))
        return {"ok":True,"sha256":digest,"image_state":"verified_original"}

    def _eligible(self, tid, item, feed_name, scan_id, now, demo):
        config=self.tenant(tid)
        text=item["title"].casefold()
        excluded=[x for x in config["excludes"] if x.casefold() in text]
        terms=config["includes"] or config["topics"]
        matched=[x for x in terms if x.casefold() in text]
        if excluded or (terms and not matched):
            return False
        link=item["url"]
        aid=hashlib.sha256((tid+":"+link).encode()).hexdigest()[:24]
        with self.connect() as con:
            present=con.execute("SELECT id FROM articles WHERE tenant_id=? AND url=?",(tid,link)).fetchone()
            if present:
                return False
            image_path, image_sha, image_state=None,None,"missing"
            if demo:
                target=self.files / tid / "images" / (aid+".jpg")
                image_sha=make_demo_image(target,item["title"],item["publisher"])
                image_path=str(target)
                image_state="demo_illustration"
            con.execute("""INSERT INTO articles
                (id,tenant_id,source_id,scan_id,title,publisher,url,published_at,
                 discovered_at,match_reason,event_key,image_path,image_sha,image_state,demo)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid,tid,feed_name["id"],scan_id,item["title"],item["publisher"],link,
                 item["published"],now,"، ".join(matched or ["الموضوع العام"]),item.get("event") or event_key(item["title"]),
                 image_path,image_sha,image_state,int(demo)))
        return True

    def run_scan(self, tid: str, scan_id: str):
        """Source errors never discard successful source results. Only caller initiated."""
        srcs=[s for s in self.sources(tid) if s["enabled"]]
        checked=matched=failures=0
        try:
            for src in srcs:
                status="ok"; error=None; count=keep=0
                try:
                    is_demo=src["feed_url"].startswith("demo://")
                    items=demo_items(src["feed_url"]) if is_demo else parse_live_feed(src["feed_url"])
                    count=len(items)
                    for item in items:
                        if self._eligible(tid,item,src,scan_id,utcnow(),is_demo):
                            keep += 1
                    checked += count; matched += keep
                except Exception as exc:
                    failures += 1; status="unavailable"
                    error=type(exc).__name__ if not isinstance(exc,RuntimeError) else str(exc)[:70]
                with self.connect() as con:
                    con.execute("INSERT INTO source_checks VALUES(?,?,?,?,?,?,?,?)",
                                (new_id(),tid,scan_id,src["id"],status,count,keep,error))
                    con.execute("""UPDATE sources SET last_ok=CASE WHEN ?='ok' THEN ? ELSE last_ok END,
                                   last_error=?,checked=checked+?,qualified=qualified+?
                                   WHERE tenant_id=? AND id=?""",
                                (status,utcnow(),error,count,keep,tid,src["id"]))
            summary={"sources_total":len(srcs),"sources_ok":len(srcs)-failures,
                     "sources_unavailable":failures,"items_inspected":checked,
                     "new_matching_coverages":matched}
            with self.connect() as con:
                con.execute("UPDATE scans SET status=?,ended_at=?,summary=? WHERE tenant_id=? AND id=?",
                            ("partial" if failures else "complete",utcnow(),json.dumps(summary),tid,scan_id))
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE scans SET status='failed',ended_at=?,summary=? WHERE tenant_id=? AND id=?",
                            (utcnow(),json.dumps({"error":type(exc).__name__}),tid,scan_id))

    def run_scan_background(self, tid, scan_id):
        thread=threading.Thread(target=self.run_scan,args=(tid,scan_id),daemon=True)
        thread.start()

    def source_checks(self, tid, scan_id):
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                """SELECT c.*,s.name FROM source_checks c JOIN sources s ON s.id=c.source_id
                   AND s.tenant_id=c.tenant_id WHERE c.tenant_id=? AND c.scan_id=?""",
                (tid,scan_id))]

    def list_reports(self, tid):
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM reports WHERE tenant_id=? ORDER BY created_at DESC LIMIT 50",(tid,))]

    def report(self, tid, rid):
        with self.connect() as con:
            row=con.execute("SELECT * FROM reports WHERE tenant_id=? AND id=?",(tid,rid)).fetchone()
        if not row:
            raise LookupError("report_not_found")
        return dict(row)

    def secure_file(self, tid: str, file: str) -> Path:
        root=(self.files / tid).resolve()
        item=Path(file).resolve()
        if not item.is_relative_to(root) or not item.is_file() or item.is_symlink():
            raise PermissionError("file_boundary_denied")
        return item

    def create_report(self, tid: str, selected: list[str], start: str, end: str) -> dict:
        tenant=self.tenant(tid)
        if not isinstance(selected,list) or len(selected)>360 or len(set(selected))!=len(selected):
            raise ValueError("invalid_report_selection")
        try:
            window_start=datetime.fromisoformat(start.replace("Z","+00:00"))
            window_end=datetime.fromisoformat(end.replace("Z","+00:00"))
            if window_start.tzinfo is None or window_end.tzinfo is None or window_start > window_end:
                raise ValueError("invalid_window")
        except (ValueError,TypeError,AttributeError):
            raise ValueError("invalid_report_window") from None
        rows=[self.article(tid,a) for a in selected]
        if any(x["state"]!="approved" for x in rows):
            raise ValueError("report_requires_approved_items")
        if any(not (window_start <= datetime.fromisoformat(x["published_at"])
                    <= window_end) for x in rows):
            raise ValueError("article_outside_report_window")
        if tenant["duplicate_policy"]=="events":
            known=set();filtered=[]
            for article in rows:
                if article["event_key"] in known: continue
                known.add(article["event_key"]); filtered.append(article)
            rows=filtered
        rows=rows[:tenant["target"]]
        file_hashes=[]
        for row in rows:
            sha=row["image_sha"]
            if row["image_path"]:
                file=self.secure_file(tid,row["image_path"])
                if hashlib.sha256(file.read_bytes()).hexdigest()!=sha:
                    raise RuntimeError("report_image_integrity_hold")
            file_hashes.append(sha)
        # Tenant logo is an input to the immutable report, not merely a
        # pathname. A later logo replacement must produce a NEW snapshot
        # while leaving every older report file unchanged.
        logo_sha=(hashlib.sha256(self.secure_file(tid,tenant["logo_path"]).read_bytes()).hexdigest()
                  if tenant.get("logo_path") else None)
        # Identical double-clicks re-use the same archived Word.
        request_obj={"ids":selected,"window":[start,end],"settings":tenant,
                     "logo_sha256":logo_sha,"images":file_hashes}
        key=hashlib.sha256(json.dumps(request_obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.connect() as con:
            existing=con.execute("SELECT * FROM reports WHERE tenant_id=? AND request_key=?",
                                 (tid,key)).fetchone()
        if existing:
            return dict(existing)
        rid=new_id()
        dest=self.files / tid / "reports"
        dest.mkdir(parents=True,exist_ok=True)
        doc=Document()
        doc.styles["Normal"].font.name="Arial"
        doc.styles["Normal"].font.size=Pt(10)
        for style in ("Title","Heading 1","Heading 2"):
            doc.styles[style].font.name="Arial"
            doc.styles[style].font.color.rgb=RGBColor(23,49,78)
        doc.styles["Title"].font.size=Pt(22 if len(tenant["name"])<48 else 18)
        doc.styles["Heading 1"].font.size=Pt(15)
        doc.styles["Heading 2"].font.size=Pt(12)
        sec=doc.sections[0]
        sec.top_margin=Inches(.7)
        sec.bottom_margin=Inches(.7)

        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        def local_date(value: str) -> str:
            # ISO timestamps in a bidi Arabic paragraph can render in the
            # wrong order. Use a native Arabic date with scoped tenant TZ.
            months=("يناير","فبراير","مارس","أبريل","مايو","يونيو",
                    "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر")
            moment=datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(
                ZoneInfo(tenant["timezone"]))
            display=(f"{moment.day} {months[moment.month-1]} {moment.year}"
                     f"، الساعة {moment.hour:02}:{moment.minute:02}")
            return display.translate(str.maketrans("0123456789","٠١٢٣٤٥٦٧٨٩"))

        def article_hyperlink(paragraph, exact_url: str, label: str):
            rel_id=paragraph.part.relate_to(exact_url,RT.HYPERLINK,is_external=True)
            link=OxmlElement("w:hyperlink")
            link.set(qn("r:id"),rel_id)
            run=OxmlElement("w:r")
            textnode=OxmlElement("w:t")
            textnode.text=label
            props=OxmlElement("w:rPr")
            color=OxmlElement("w:color")
            color.set(qn("w:val"),"21617A")
            props.append(color)
            under=OxmlElement("w:u")
            under.set(qn("w:val"),"single")
            props.append(under)
            run.insert(0,props)
            run.append(textnode)
            link.append(run)
            paragraph._p.append(link)

        if tenant.get("logo_path"):
            try:
                logo=self.secure_file(tid,tenant["logo_path"])
                doc.add_picture(str(logo),width=Inches(1))
            except (PermissionError,OSError):
                raise RuntimeError("report_logo_integrity_hold") from None

        doc.add_heading("رصد | "+tenant["name"],0)
        doc.add_paragraph("تقرير إعلامي مخصص للجهة — إصدار محفوظ يمكن الرجوع إليه بعد تغيير الإعدادات.")
        doc.add_heading("نطاق التقرير",level=2)
        is_demo=any(a["demo"] for a in rows) or tenant.get("mode")=="demo"
        doc.add_paragraph("وضع التقرير: "+
            ("عرض تجريبي — بيانات وأخبار وصور غير حقيقية" if is_demo
             else "رصد حي — روابط ناشرين أصليين (التوثيق بحسب حالة كل صورة)"))
        doc.add_paragraph("نافذة التقرير المنشورة: من "+local_date(start)+" إلى "+
                          local_date(end)+"، بالتوقيت المحلي للجهة.")
        doc.add_paragraph("التغطيات: "+str(len(rows))+
                          " | الأحداث المستقلة: "+str(len({a["event_key"] for a in rows}))+
                          " | الناشرون: "+str(len({a["publisher"] for a in rows})))
        doc.add_paragraph("صور ناشر أصلية موثقة: "+
                          str(sum(a["image_state"]=="verified_original" for a in rows)))
        doc.add_heading("أدلة آخر فحص للمصادر",level=2)
        scans=self.list_scans(tid,1)
        if scans:
            last=json.loads(scans[0].get("summary") or "{}")
            if last.get("window_start") and last.get("window_end"):
                doc.add_paragraph("نافذة آخر فحص RSS للجهة: من "+
                    local_date(last["window_start"])+" إلى "+
                    local_date(last["window_end"])+
                    "؛ لا تعني أن جميع مصادر الإنترنت غُطّيت.")
                doc.add_paragraph("آخر فحص — مصادر نجحت: "+str(last.get("sources_ok",0))+
                    " | المصادر المتعذرة: "+str(last.get("sources_unavailable",0))+
                    " | المواد المقروءة: "+str(last.get("items_inspected",0))+
                    " | المواد خارج الفترة: "+str(last.get("outside_window",0)))
            failed=int(last.get("sources_unavailable") or 0)
            if failed:
                doc.add_paragraph("حدود التغطية: تعذر فحص "+str(failed)+
                                  " مصدر/مصادر خلال آخر فحص؛ النتائج جزئية ولا تثبت عدم نشر مواد أخرى.")
        # Count the actual stored tenant publications in this report window,
        # not the target and not the most recent unrelated source attempt.
        with self.connect() as con:
            candidates=con.execute("SELECT published_at,state FROM articles WHERE tenant_id=?",(tid,)).fetchall()
        within=[a for a in candidates if window_start <= datetime.fromisoformat(a["published_at"]) <= window_end]
        doc.add_paragraph("التغطيات المحفوظة داخل فترة التقرير: "+str(len(within))+
            " | معتمدة: "+str(sum(a["state"]=="approved" for a in within))+
            " | معلقة: "+str(sum(a["state"]=="pending" for a in within))+
            " | مستبعدة: "+str(sum(a["state"]=="rejected" for a in within))+
            " | دخلت الملف بعد الاختيار وسياسة التكرار والهدف: "+str(len(rows)))
        if len(rows)<tenant["target"]:
            doc.add_paragraph("مقارنة بالهدف: اختار المحلل "+
                str(len(rows))+" خبرًا لهذا الملف من هدف "+str(tenant["target"])+
                " أخبار للجهة. هذا الفرق لا يثبت نقص تغطية المصادر؛ "+
                "راجع نطاق الناشرين ونتيجة الفحص والمواد المعلقة للمراجعة.")

        # Rights are tracked for each individual source, never assumed from
        # successful publisher access or a cryptographically verified picture.
        source_rights={x["id"]:x for x in self.sources(tid)}
        # An intentional, clearly identified cover page. Keep one complete
        # publisher-evidence card together; never strand its title on cover.
        if rows:
            doc.add_paragraph("تنبيه: صور صفحات الناشرين للتوثيق الداخلي؛ إعادة النشر التجاري تحتاج مراجعة حقوق المصدر.")
            doc.add_page_break()
            doc.add_heading("الأخبار المُختارة وروابط الناشرين",level=1)

        for idx,art in enumerate(rows,1):
            # One single Word row per report card. w:cantSplit keeps the
            # title, publisher, hyperlink, genuine/DEMO image and SHA
            # together even at a page boundary and for longer titles.
            table=doc.add_table(rows=1,cols=1)
            table.autofit=False
            row=table.rows[0]
            props=row._tr.get_or_add_trPr()
            nosplit=OxmlElement("w:cantSplit")
            props.append(nosplit)
            cell=row.cells[0]
            heading=cell.paragraphs[0]
            heading.paragraph_format.keep_with_next=True
            title_run=heading.add_run(str(idx)+" | "+art["title"])
            title_run.bold=True
            title_run.font.size=Pt(13)
            meta=cell.add_paragraph(art["publisher"]+" — نُشر "+
                                    local_date(art["published_at"]))
            meta.paragraph_format.keep_with_next=True
            cell.add_paragraph("اكتُشف "+local_date(art["discovered_at"])).paragraph_format.keep_with_next=True
            linkpara=cell.add_paragraph("المصدر الأصلي: ")
            linkpara.paragraph_format.keep_with_next=True
            article_hyperlink(linkpara,art["url"],"فتح الخبر على موقع "+art["publisher"])
            if art["image_path"]:
                photo=cell.add_paragraph("الصورة: "+
                    ("DEMO — صورة توضيحية وليست صورة الناشر" if art["demo"]
                     else "لقطة صفحة الناشر الأصلية — حالة التحقق: "+art["image_state"]))
                photo.paragraph_format.keep_with_next=True
                picture=cell.add_paragraph()
                picture.paragraph_format.keep_with_next=True
                picture.add_run().add_picture(
                    str(self.secure_file(tid,art["image_path"])),width=Inches(4.7))
                cell.add_paragraph("بصمة JPEG — SHA-256: "+art["image_sha"])
                source=source_rights.get(art["source_id"],{})
                cell.add_paragraph("حقوق إعادة استخدام صورة الناشر — "+
                    str(source.get("name",art["publisher"]))+
                    ": لم يقدم تصريح إعادة نشر تجاري موثق في بيانات رصد؛ "+
                    "تحقق من موافقة الناشر قبل المشاركة الخارجية.")
            else:
                cell.add_paragraph("لا توجد صورة ناشر موثقة لهذا الخبر.")
            doc.add_paragraph("").paragraph_format.space_after=Pt(3)

        # Explicit Arabic run direction and alignment for every paragraph,
        # including ones inside table cells (not just document.paragraphs).
        paragraphs=list(doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.extend(cell.paragraphs)
        for paragraph in paragraphs:
            paragraph.alignment=WD_ALIGN_PARAGRAPH.RIGHT
            bidi=OxmlElement("w:bidi")
            bidi.set(qn("w:val"),"1")
            paragraph._p.get_or_add_pPr().append(bidi)
        footer=sec.footer.paragraphs[0]
        footer.text="رصد | "+tenant["name"]+" — محفوظ في أرشيف الجهة"
        footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        for run in footer.runs:
            run.font.size=Pt(8)
        path=dest/(rid+".docx")
        doc.save(path)
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest=[{"id":r["id"],"title":r["title"],"publisher":r["publisher"],
                   "url":r["url"],"published_at":r["published_at"],
                   "discovered_at":r["discovered_at"],"image_sha":r["image_sha"],
                   "image_state":r["image_state"],"event_key":r["event_key"]} for r in rows]
        meta=json.dumps(manifest,ensure_ascii=False)
        settings=json.dumps({**tenant,"logo_sha256":logo_sha},ensure_ascii=False)
        with self.connect() as con:
            try:
                con.execute("""INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?,?)""",
                            (rid,tid,utcnow(),start,end,str(path),sha,meta,settings,key))
            except sqlite3.IntegrityError:
                path.unlink(missing_ok=True)
                previous=con.execute("SELECT * FROM reports WHERE tenant_id=? AND request_key=?",
                                     (tid,key)).fetchone()
                return dict(previous)
        return self.report(tid,rid)

    def seed_demo(self, owner_email="owner@rasd.demo", owner_password=None):
        with self.connect() as con:
            row=con.execute("SELECT COUNT(*) AS n FROM users").fetchone()
            if row["n"]:
                return None
        password=owner_password or secrets.token_urlsafe(19)
        owner=self.create_user(owner_email,password,owner=True)
        uni=self.create_tenant("جامعة الريادة — تجريبي",topics=["التعليم العالي","البحث العلمي"],
                               includes=["الجامعات","طلاب","البحث"],target=10,
                               duplicate_policy="coverages")
        food=self.create_tenant("شركة الغذاء — تجريبي",topics=["الصناعات الغذائية"],
                                includes=["الأغذية","الغذائي"],target=10,
                                duplicate_policy="coverages")
        empty=self.create_tenant("جهة جديدة — بلا بيانات",topics=["قطاع جديد"],includes=["غير موجود"])
        self.add_source(uni,"مواقع التعليم — بيانات توضيحية","demo://university")
        self.add_source(uni,"مصدر متعذر تجريبي","demo://unavailable")
        self.add_source(food,"مصادر الأغذية — بيانات توضيحية","demo://foods")
        # Ministry stays an independent tenant config, NO transfer of mail or ledger.
        try:
            source=json.loads((ROOT/"sources_newsroom_active.json").read_text(encoding="utf-8"))
            ministry=self.create_tenant("وزارة التخطيط — ملف مستقل",topics=["التخطيط والتنمية"],
                  includes=source.get("keywords",[])[:50],target=10,duplicate_policy="events")
            for item in source.get("feeds",[]):
                if item.get("url") in __import__("monitor").APPROVED_FEED_URLS:
                    self.add_source(ministry,item.get("name","ناشر"),item["url"])
        except (OSError,ValueError,KeyError,sqlite3.IntegrityError):
            pass
        return {"owner_email":owner_email,"owner_password":password,
                "tenants":{"university":uni,"foods":food,"empty":empty}}
