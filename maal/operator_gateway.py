"""MA'AL test-only, E-only authenticated human operator gateway.

No web exposure of owner challenge, no model tool access, no customer accounts.
A real human must enter the test password again to authorize an internal draft.
"""
from __future__ import annotations
import hashlib,hmac,secrets,sqlite3
from datetime import datetime,timezone,timedelta
from pathlib import Path

from maal.internal_actions import TaskStore,utc,sha

def password_digest(password:str,salt:bytes)->bytes:
    return hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,350000)

class OperatorGateway:
    def __init__(self,db_file:Path):
        self.store=TaskStore(db_file)
        with self.store.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS demo_users(
                login TEXT PRIMARY KEY,
                tenant TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('OWNER','REVIEWER')),
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_sessions(
                token_hash TEXT PRIMARY KEY,
                login TEXT NOT NULL REFERENCES demo_users(login),
                csrf TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_task_owners(
                draft_id TEXT PRIMARY KEY REFERENCES drafts(draft_id),
                login TEXT NOT NULL REFERENCES demo_users(login),
                tenant TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_auth_attempts(
                login TEXT NOT NULL PRIMARY KEY,
                count INTEGER NOT NULL,
                reset_after TEXT NOT NULL
            );
            """)
    def provision(self,login:str,tenant:str,role:str,password:str)->None:
        if not(login and tenant and role in {"OWNER","REVIEWER"}
               and len(login)<=70 and len(tenant)<=70 and len(password)>=20):
            raise ValueError("invalid_test_account")
        salt=secrets.token_bytes(20)
        with self.store.db() as db:
            db.execute("INSERT INTO demo_users(login,tenant,role,password_salt,password_hash) VALUES(?,?,?,?,?)",
                       (login,tenant,role,salt,password_digest(password,salt)))

    def _verify_password(self,db,login,password)->bool:
        row=db.execute("SELECT password_salt,password_hash FROM demo_users WHERE login=?",(login,)).fetchone()
        if row is None:
            password_digest(password,secrets.token_bytes(20))
            return False
        return hmac.compare_digest(password_digest(password,row["password_salt"]),row["password_hash"])

    def login(self,username:str,password:str)->tuple[str,str]:
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>80 or len(password)>180:
            raise PermissionError("invalid_login")
        denied=None;credential=None
        with self.store.db() as db:
            row=db.execute("SELECT count,reset_after FROM demo_auth_attempts WHERE login=?",(username,)).fetchone()
            now=utc()
            if row and row["count"]>=6 and row["reset_after"]>now:
                denied="rate_limited"
            elif not self._verify_password(db,username,password):
                count=row["count"] if row and row["reset_after"]>now else 0
                reset=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()
                db.execute("INSERT INTO demo_auth_attempts(login,count,reset_after) VALUES(?,?,?) "
                           "ON CONFLICT(login) DO UPDATE SET count=?,reset_after=?",
                           (username,count+1,reset,count+1,reset))
                denied="invalid_login"
            else:
                db.execute("DELETE FROM demo_auth_attempts WHERE login=?",(username,))
                token=secrets.token_urlsafe(35)
                csrf=secrets.token_urlsafe(30)
                exp=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
                db.execute("INSERT INTO demo_sessions(token_hash,login,csrf,expires_at) VALUES(?,?,?,?)",
                           (sha(token),username,csrf,exp))
                credential=(token,csrf)
        if denied is not None: raise PermissionError(denied)
        assert credential is not None
        return credential

    def whoami(self,token:str)->dict:
        if not token or len(token)>180:raise PermissionError("no_session")
        with self.store.db() as db:
            row=db.execute("""SELECT u.login,u.tenant,u.role,s.csrf,s.expires_at
                 FROM demo_sessions s JOIN demo_users u ON u.login=s.login
                 WHERE s.token_hash=?""",(sha(token),)).fetchone()
            if not row or row["expires_at"]<=utc():
                raise PermissionError("session_expired")
            return dict(row)

    def require(self,token:str,csrf:str|None=None)->dict:
        actor=self.whoami(token)
        if csrf is not None and (not isinstance(csrf,str) or
                not hmac.compare_digest(actor["csrf"],csrf)):
            raise PermissionError("csrf_token_required")
        return actor

    def logout(self,token:str)->None:
        with self.store.db() as db:
            db.execute("DELETE FROM demo_sessions WHERE token_hash=?",(sha(token),))

    def create(self,token,csrf,evidence,description,key,model_run_id=None)->str:
        actor=self.require(token,csrf)
        if actor["role"] not in {"OWNER","REVIEWER"}:
            raise PermissionError("not_allowed")
        if not isinstance(key,str) or not 12<=len(key)<=100:
            raise ValueError("idempotency_key_required")
        draft=self.store.create_draft(evidence,description,sha(actor["login"]+"|"+actor["tenant"]+"|"+key),model_run_id=model_run_id)
        with self.store.db() as db:
            owner=db.execute("SELECT login,tenant FROM demo_task_owners WHERE draft_id=?",(draft,)).fetchone()
            if owner and (owner["login"]!=actor["login"] or owner["tenant"]!=actor["tenant"]):
                raise PermissionError("cross_tenant_draft")
            db.execute("INSERT OR IGNORE INTO demo_task_owners(draft_id,login,tenant) VALUES(?,?,?)",
                       (draft,actor["login"],actor["tenant"]))
        return draft

    def _owner_draft(self,actor,draft_id):
        if not isinstance(draft_id,str) or len(draft_id)>60:
            raise PermissionError("draft_not_accessible")
        with self.store.db() as db:
            own=db.execute("SELECT 1 FROM demo_task_owners WHERE draft_id=? AND login=? AND tenant=?",
                           (draft_id,actor["login"],actor["tenant"])).fetchone()
        if not own:raise PermissionError("draft_not_accessible")

    def approve(self,token,csrf,draft_id,stepup_password):
        actor=self.require(token,csrf)
        if actor["role"]!="OWNER":raise PermissionError("approval_restricted_to_owner")
        self._owner_draft(actor,draft_id)
        with self.store.db() as db:
            verified=self._verify_password(db,actor["login"],stepup_password)
        if not verified:raise PermissionError("stepup_authentication_failed")
        challenge=self.store.issue_owner_challenge(draft_id)
        self.store.approve(draft_id,"OWNER",challenge,principal=actor["login"])
        return {"draft_id":draft_id,"state":"APPROVED_BY_AUTHENTICATED_TEST_OWNER",
                "approved_by":actor["login"],"production_approval":False}

    def reject(self,token,csrf,draft_id,stepup_password,reason):
        actor=self.require(token,csrf)
        if actor["role"]!="OWNER":raise PermissionError("rejection_restricted_to_owner")
        self._owner_draft(actor,draft_id)
        with self.store.db() as db:
            verified=self._verify_password(db,actor["login"],stepup_password)
        if not verified:raise PermissionError("stepup_authentication_failed")
        return {"draft_id":draft_id,
                "state":self.store.reject(draft_id,actor["login"],reason),
                "approved_by":None,"task_created":False,"external_action":False}

    def execute(self,token,csrf,draft_id):
        actor=self.require(token,csrf)
        if actor["role"]!="OWNER":raise PermissionError("execute_restricted_to_owner")
        self._owner_draft(actor,draft_id)
        task_id=self.store.execute(draft_id)
        return {"draft_id":draft_id,"task_id":task_id,
                "state":"INTERNAL_TEST_TASK_EXECUTED","external_action":False}

    def dashboard(self,token):
        actor=self.require(token)
        with self.store.db() as db:
            drafts=[dict(row) for row in db.execute("""
                SELECT d.draft_id,d.evidence_id,d.description,d.state,d.created_at,d.approved_by,
                       t.task_id,t.created_at AS executed_at
                FROM drafts d JOIN demo_task_owners o ON o.draft_id=d.draft_id
                LEFT JOIN tasks t ON t.draft_id=d.draft_id
                WHERE o.login=? AND o.tenant=?
                ORDER BY d.created_at DESC LIMIT 40
            """,(actor["login"],actor["tenant"]))]
            events=[dict(row) for row in db.execute("""
                SELECT a.sequence,a.timestamp,a.draft_id,a.event,a.actor
                FROM audit a JOIN demo_task_owners o ON o.draft_id=a.draft_id
                WHERE o.login=? AND o.tenant=?
                ORDER BY a.sequence DESC LIMIT 80
            """,(actor["login"],actor["tenant"]))]
        return {"operator":actor["login"],"tenant":actor["tenant"],"role":actor["role"],
                "csrf":actor["csrf"],"drafts":drafts,"audit":events,
                "audit_integrity":self.store.verify_audit()["integrity"],
                "production":False}
