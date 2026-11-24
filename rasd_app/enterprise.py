"""Manual enterprise trial, extending the proven PR195 store without touching scheduler.

Upgrades: bounded publisher-time windows, honest per-source reasons, conservative
event grouping, signed image evidence outcomes and strict live/demo separation.
Existing demo databases are migrated additively. No mail or production CAS.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import (Store, DEMO_FEEDS, ROLES, digest_password, clean_terms, demo_items, event_key,
                   make_demo_image, new_id, parse_live_feed, utcnow)
from monitor import _matchable_arabic, safe_source_failure_code

UTC=timezone.utc
_STOP={"في","من","عن","على","الى","إلى","بعد","قبل","مع","أن","إن","قال","يقول",
       "أعلن","أعلنت","يعلن","وتعلن","بشأن","حول","جديد","الجديد","المصرية",
       "وال","مصر","لدى","وفقا","خلال","اليوم","العام","الأول","الاول","آخر",
       "والذي","التي","حيث","قد","جرى","تم","و","ب","ال"}
_TOKEN=re.compile(r"[\w\u0600-\u06FF]+",re.UNICODE)
_CAIRO=ZoneInfo("Africa/Cairo")


def _words(title: str) -> tuple[set[str],set[str]]:
    normalized=_matchable_arabic(title)
    tokens=[]
    for token in _TOKEN.findall(normalized):
        token="".join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in token)
        if len(token)>=3 and token not in _STOP:
            tokens.append(token)
    numbers={x for x in tokens if any(c.isdigit() for c in x)}
    return set(tokens),numbers


def _same_event(left: str, right: str) -> bool:
    """Conservative candidate only; never assert semantic equivalence."""
    a,na=_words(left)
    b,nb=_words(right)
    if na!=nb or len(a&b)<4 or min(len(a),len(b))<5:
        return False
    return len(a&b)/len(a|b)>=0.70


def _window(start, end):
    if start is None and end is None:
        stop=datetime.now(UTC)
        return (stop-timedelta(hours=48)).isoformat(),stop.isoformat()
    try:
        a=datetime.fromisoformat(str(start).replace("Z","+00:00"))
        b=datetime.fromisoformat(str(end).replace("Z","+00:00"))
        if a.tzinfo is None or b.tzinfo is None or a>=b:
            raise ValueError
        if b-a>timedelta(days=31) or b>datetime.now(UTC)+timedelta(minutes=10):
            raise ValueError
        return a.astimezone(UTC).isoformat(),b.astimezone(UTC).isoformat()
    except (ValueError,TypeError,OverflowError,AttributeError):
        raise ValueError("invalid_scan_window_timezone_order_or_31day_limit") from None


class EnterpriseStore(Store):
    def __init__(self,base,*,live_only=False):
        self.live_only=bool(live_only)
        super().__init__(base)
        with self.connect() as db:
            for table,column,dtype in (
                ("scans","window_start","TEXT"),
                ("scans","window_end","TEXT"),
                ("source_checks","checked_at","TEXT"),
                ("source_checks","excluded","INTEGER NOT NULL DEFAULT 0"),
                ("source_checks","outside_window","INTEGER NOT NULL DEFAULT 0"),
                ("source_checks","already_known","INTEGER NOT NULL DEFAULT 0"),
                ("sources","reuse_rights","TEXT NOT NULL DEFAULT 'unreviewed'"),
                ("users","disabled","INTEGER NOT NULL DEFAULT 0"),
                ("memberships","active","INTEGER NOT NULL DEFAULT 1"),
                ("articles","image_error","TEXT"),
                ("articles","image_checked_at","TEXT"),
            ):
                columns={row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                if column not in columns:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {dtype}")
            # Database created by the prior local demo can contain a scan that
            # was terminated at process shutdown. Do not silently call it success.
            db.execute("""UPDATE scans SET status='failed',ended_at=?,
                summary='{"error":"interrupted_by_app_restart","source_results_preserved":true}'
                WHERE status='running'""",(utcnow(),))

    def session_user(self,token,csrf=None):
        user=super().session_user(token,csrf)
        if user is not None and user.get("disabled"):
            return None
        return user

    def login(self,email,password):
        token,csrf=super().login(email,password)
        if not self.session_user(token,csrf):
            self.logout(token)
            raise PermissionError("account_disabled")
        return token,csrf

    def memberships(self,user):
        if user.get("disabled"):
            return []
        if user.get("platform_owner"):
            return super().memberships(user)
        with self.connect() as db:
            rows=db.execute("""SELECT t.*,m.role FROM tenants t
                JOIN memberships m ON m.tenant_id=t.id
                WHERE m.user_id=? AND m.active=1 ORDER BY t.name""",
                (user["id"],)).fetchall()
        return [dict(row) for row in rows]

    def role(self,user,tenant,required="reader"):
        if user.get("disabled"):
            raise PermissionError("account_disabled")
        if not user.get("platform_owner"):
            with self.connect() as db:
                row=db.execute("SELECT active FROM memberships WHERE tenant_id=? AND user_id=?",
                               (tenant,user["id"])).fetchone()
            if row is None or not row["active"]:
                raise PermissionError("tenant_membership_disabled")
        return super().role(user,tenant,required)

    def add_member(self,tid,email,password,role):
        if role not in ROLES:
            raise ValueError("role_invalid")
        normalized=str(email).strip().lower()
        with self.connect() as db:
            row=db.execute("SELECT id FROM users WHERE email=?",(normalized,)).fetchone()
        uid=row["id"] if row else self.create_user(normalized,password)
        with self.connect() as db:
            db.execute("""INSERT INTO memberships(user_id,tenant_id,role,active)
                VALUES(?,?,?,1)""",(uid,tid,role))
        return uid

    def tenant_members(self,tid):
        with self.connect() as db:
            rows=db.execute("""SELECT u.id,u.email,m.role,m.active
                FROM memberships m JOIN users u ON u.id=m.user_id
                WHERE m.tenant_id=? ORDER BY u.email""",(tid,)).fetchall()
        return [dict(r) for r in rows]

    def toggle_member(self,tid,uid,enabled,actor):
        if type(enabled) is not bool:
            raise ValueError("invalid_member_status")
        if uid==actor["id"]:
            raise ValueError("cannot_disable_own_membership")
        with self.connect() as db:
            u=db.execute("SELECT platform_owner FROM users WHERE id=?",(uid,)).fetchone()
            if u is None or u["platform_owner"]:
                raise PermissionError("protected_owner_account")
            row=db.execute("SELECT role,active FROM memberships WHERE tenant_id=? AND user_id=?",
                           (tid,uid)).fetchone()
            if row is None:
                raise LookupError("member_not_in_tenant")
            if not enabled and row["role"]=="tenant_admin" and not actor["platform_owner"]:
                others=db.execute("""SELECT COUNT(*) FROM memberships
                   WHERE tenant_id=? AND active=1 AND role='tenant_admin' AND user_id<>?""",
                   (tid,uid)).fetchone()[0]
                if others==0:
                    raise ValueError("cannot_disable_last_tenant_admin")
            db.execute("UPDATE memberships SET active=? WHERE tenant_id=? AND user_id=?",
                       (int(enabled),tid,uid))
            if not enabled:
                db.execute("DELETE FROM sessions WHERE user_id=?",(uid,))
        return {"member_id":uid,"enabled":enabled}

    def change_password(self,uid,current_password,new_password):
        if not isinstance(new_password,str) or not 14<=len(new_password)<=256:
            raise ValueError("new_password_must_have_14_to_256_characters")
        with self.connect() as db:
            row=db.execute("SELECT salt,password_hash,disabled FROM users WHERE id=?",(uid,)).fetchone()
            if row is None or row["disabled"]:
                raise PermissionError("account_disabled")
            if not isinstance(current_password,str) or not hmac.compare_digest(
                row["password_hash"],digest_password(current_password,row["salt"])):
                raise PermissionError("current_password_wrong")
            if hmac.compare_digest(row["password_hash"],digest_password(new_password,row["salt"])):
                raise ValueError("new_password_must_differ")
            salt=secrets.token_hex(16)
            db.execute("UPDATE users SET salt=?,password_hash=? WHERE id=?",
                       (salt,digest_password(new_password,salt),uid))
            db.execute("DELETE FROM sessions WHERE user_id=?",(uid,))
        return True

    def tenant(self,tid):
        result=super().tenant(tid)
        with self.connect() as db:
            groups=[r["feed_url"] for r in db.execute(
                "SELECT feed_url FROM sources WHERE tenant_id=?",(tid,))]
        demo=any(x.startswith("demo://") for x in groups)
        result["mode"]="demo" if demo else "live"
        return result

    def add_source(self,tenant,name,feed):
        if self.live_only and feed in DEMO_FEEDS:
            raise ValueError("demo_source_forbidden_in_private_live")
        existing=self.sources(tenant)
        if existing and any(s["feed_url"].startswith("demo://")!=feed.startswith("demo://")
                            for s in existing):
            raise ValueError("cannot_mix_demo_and_live_sources")
        return super().add_source(tenant,name,feed)

    def start_scan(self,tid,window_start=None,window_end=None):
        # Fixed-date synthetic fixture remains reproducible in future CI
        # without altering LIVE scans (which always use the actual UTC clock).
        if window_start is None and window_end is None and self.tenant(tid)["mode"]=="demo":
            start=datetime(2026,11,22,tzinfo=_CAIRO).astimezone(UTC).isoformat()
            end=datetime(2026,11,25,tzinfo=_CAIRO).astimezone(UTC).isoformat()
        else:
            start,end=_window(window_start,window_end)
        sid,created=super().start_scan(tid)
        if created:
            with self.connect() as db:
                db.execute("UPDATE scans SET window_start=?,window_end=? WHERE tenant_id=? AND id=?",
                           (start,end,tid,sid))
        return sid,created

    @staticmethod
    def match_title(title: str, tenant: dict) -> tuple[str,list[str]]:
        norm=_matchable_arabic(title)
        excluded=[x for x in tenant["excludes"] if _matchable_arabic(x) in norm]
        if excluded:
            return "excluded_by_keyword",excluded
        terms=tenant["includes"] or tenant["topics"]
        matched=[x for x in terms if _matchable_arabic(x) in norm]
        if terms and not matched:
            return "no_topic_match",[]
        return "matched",matched or ["نطاق عام بلا كلمات تضمين"]

    def _event_for(self,tid,item):
        if item.get("event","").startswith("demo-"):
            return item["event"]
        incoming=datetime.fromisoformat(item["published"]).astimezone(UTC)
        with self.connect() as db:
            candidates=db.execute("""SELECT title,published_at,event_key FROM articles
                WHERE tenant_id=? AND published_at>=? AND published_at<=?
                ORDER BY discovered_at ASC LIMIT 500""",(
                    tid,(incoming-timedelta(hours=48)).isoformat(),
                    (incoming+timedelta(hours=48)).isoformat())).fetchall()
        for old in candidates:
            if _same_event(item["title"],old["title"]):
                return old["event_key"]
        return event_key(item["title"])

    def _save_item(self,tid,source,sid,item,reason,demo):
        if self.live_only and demo:
            raise ValueError("demo_item_forbidden_in_private_live")
        url=item["url"]
        aid=hashlib.sha256((tid+":"+url).encode()).hexdigest()[:24]
        with self.connect() as db:
            if db.execute("SELECT 1 FROM articles WHERE tenant_id=? AND url=?",(tid,url)).fetchone():
                return False
        image_path=image_sha=None
        image_state="missing"
        if demo:
            path=self.files/tid/"images"/(aid+".jpg")
            image_sha=make_demo_image(path,item["title"],item["publisher"])
            image_path=str(path);image_state="demo_illustration"
        group=self._event_for(tid,item)
        with self.connect() as db:
            try:
                db.execute("""INSERT INTO articles(
                    id,tenant_id,source_id,scan_id,title,publisher,url,published_at,
                    discovered_at,match_reason,state,event_key,image_path,image_sha,
                    image_state,demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
                    aid,tid,source["id"],sid,item["title"],item["publisher"],url,
                    item["published"],utcnow(),"، ".join(reason),"pending",
                    group,image_path,image_sha,image_state,int(demo)))
                return True
            except sqlite3.IntegrityError:
                return False

    def run_scan(self,tid,sid):
        """Every successful source survives an independent failure. No DEMO fallback."""
        with self.connect() as db:
            scan=db.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?",
                            (tid,sid)).fetchone()
        if not scan:
            raise LookupError("tenant_scan_not_found")
        begin=scan["window_start"] or (datetime.now(UTC)-timedelta(hours=48)).isoformat()
        end=scan["window_end"] or datetime.now(UTC).isoformat()
        start_dt=datetime.fromisoformat(begin)
        end_dt=datetime.fromisoformat(end)
        tenant=self.tenant(tid)
        srcs=[x for x in self.sources(tid) if x["enabled"]]
        total=qualified=failures=filtered=outside=known=0
        try:
            for source in srcs:
                demo=source["feed_url"].startswith("demo://")
                count=matched=excl=out=already=0;status="ok";failure=None
                try:
                    if self.live_only and demo:
                        raise ValueError("demo_forbidden_private_live")
                    records=demo_items(source["feed_url"]) if demo else parse_live_feed(source["feed_url"])
                    count=len(records)
                    for item in records:
                        published=datetime.fromisoformat(item["published"].replace("Z","+00:00"))
                        if not start_dt<=published<=end_dt:
                            out+=1;continue
                        category,reason=self.match_title(item["title"],tenant)
                        if category!="matched":
                            excl+=1;continue
                        if self._save_item(tid,source,sid,item,reason,demo):
                            matched+=1
                        else:
                            already+=1
                except Exception as err:
                    status="unavailable";failures+=1
                    # Never include raw third-party exception, credentials or HTML.
                    code=safe_source_failure_code(err)
                    failure=(str(err) if (demo and isinstance(err,RuntimeError))
                             else code if code!="other" else type(err).__name__)
                    failure=str(failure)[:75]
                checked_at=utcnow()
                with self.connect() as db:
                    db.execute("""INSERT INTO source_checks
                        (id,tenant_id,scan_id,source_id,status,scanned,matched,reason,
                         checked_at,excluded,outside_window,already_known)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(
                         new_id(),tid,sid,source["id"],status,count,matched,failure,
                         checked_at,excl,out,already))
                    db.execute("""UPDATE sources SET
                        last_ok=CASE WHEN ?='ok' THEN ? ELSE last_ok END,
                        last_error=?,checked=checked+?,qualified=qualified+?
                        WHERE tenant_id=? AND id=?""",
                        (status,checked_at,failure,count,matched,tid,source["id"]))
                total+=count;qualified+=matched;filtered+=excl;outside+=out;known+=already
            summary={"sources_total":len(srcs),"sources_ok":len(srcs)-failures,
                "sources_unavailable":failures,"items_inspected":total,
                "new_matching_coverages":qualified,"excluded_or_unmatched":filtered,
                "outside_window":outside,"already_known":known,
                "window_start":begin,"window_end":end,
                "mode":tenant["mode"],"source_checks_recorded":len(srcs)}
            with self.connect() as db:
                db.execute("""UPDATE scans SET status=?,ended_at=?,summary=?
                    WHERE tenant_id=? AND id=?""",(
                    "partial" if failures else "complete",utcnow(),
                    json.dumps(summary,ensure_ascii=False),tid,sid))
        except Exception as err:
            with self.connect() as db:
                db.execute("""UPDATE scans SET status='failed',ended_at=?,summary=?
                    WHERE tenant_id=? AND id=?""",(
                    utcnow(),json.dumps({"error":type(err).__name__,
                        "source_results_preserved":True},ensure_ascii=False),tid,sid))

    def capture_original(self,tid,aid):
        result=super().capture_original(tid,aid)
        reason=None if result.get("ok") else result.get("reason","capture_failed")
        with self.connect() as db:
            db.execute("""UPDATE articles SET image_error=?,image_checked_at=?
                WHERE tenant_id=? AND id=?""",(reason,utcnow(),tid,aid))
        return result

    def review(self,tid,aid,actor,state,event=None,reason=None):
        if state=="rejected" and not str(reason or "").strip():
            raise ValueError("rejection_reason_required")
        super().review(tid,aid,actor,state,event)
        if reason:
            article=self.article(tid,aid)
            history=json.loads(article["review_log"])
            history[-1]["reason"]=str(reason).strip()[:500]
            with self.connect() as db:
                db.execute("UPDATE articles SET review_log=? WHERE tenant_id=? AND id=?",
                           (json.dumps(history,ensure_ascii=False),tid,aid))

    def articles(self,tid,*,event_key=None,scan_id=None,image_state=None,source_id=None,**filters):
        rows=super().articles(tid,**filters)
        if event_key:
            rows=[r for r in rows if r["event_key"]==event_key]
        if scan_id:
            rows=[r for r in rows if r["scan_id"]==scan_id]
        if image_state:
            rows=[r for r in rows if r["image_state"]==image_state]
        if source_id:
            rows=[r for r in rows if r["source_id"]==source_id]
        return rows
