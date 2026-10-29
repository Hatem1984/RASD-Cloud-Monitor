"""MA'AL Gate F — owner-local internal draft task, explicit review, idempotent execution.

Test-only; never Gmail, GitHub, web requests, production tables, paid APIs.
Approval issuance is NOT exposed in the web/AI-facing API.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from maal.decision_contracts import Evidence

AUTHORIZED_ROLES = frozenset({"OWNER", "REVIEWER"})

def utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

class TaskStore:
    """An E-only isolated SQLite event chain. Not a production approval service."""
    def __init__(self, file: Path) -> None:
        self.path=file.resolve()
        if self.path.drive.upper() != "E:" or "MAAL" not in self.path.parts:
            raise ValueError("Gate_F_test_store_must_be_under_E_MAAL")
        if "01_ACTIVE_CODE" in self.path.parts:
            raise ValueError("action_db_must_not_be_inside_public_git_code")
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS drafts(
                draft_id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE NOT NULL,
                evidence_id TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                description TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                approval_secret_hash TEXT,
                approved_by TEXT,
                state TEXT NOT NULL CHECK(state IN ('DRAFT','APPROVED','EXECUTED','REJECTED')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks(
                task_id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL UNIQUE REFERENCES drafts(draft_id),
                description TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                draft_id TEXT NOT NULL,
                event TEXT NOT NULL,
                actor TEXT NOT NULL,
                metadata TEXT NOT NULL,
                prev_sha256 TEXT NOT NULL,
                hash_sha256 TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS audit_no_update
              BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'audit_is_append_only');END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete
              BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'audit_is_append_only');END;
            """)
    @contextmanager
    def db(self):
        connection=sqlite3.connect(self.path,timeout=20)
        try:
            connection.row_factory=sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=20000")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _audit(self,conn,draft_id,event,actor,metadata):
        last=conn.execute("SELECT hash_sha256 FROM audit ORDER BY sequence DESC LIMIT 1").fetchone()
        prev=last["hash_sha256"] if last else "0"*64
        record={"timestamp":utc(),"draft_id":draft_id,
                "event":event,"actor":actor,"metadata":metadata,"prev":prev}
        digest=sha(canonical(record))
        conn.execute("""INSERT INTO audit
          (timestamp,draft_id,event,actor,metadata,prev_sha256,hash_sha256)
          VALUES(?,?,?,?,?,?,?)""",
          (record["timestamp"],draft_id,event,actor,canonical(metadata),prev,digest))

    def create_draft(self,evidence:Evidence,description:str,idempotency_key:str,model_run_id:str|None=None)->str:
        evidence.validate()
        if not description.strip() or len(description)>500 or len(idempotency_key)<12:
            raise ValueError("invalid_task_draft_or_idempotency_key")
        if model_run_id is not None and (not isinstance(model_run_id,str) or
                not model_run_id.startswith(("maal-g3-","maal-open-","maal-paired-")) or len(model_run_id)>100):
            raise ValueError("invalid_model_run_reference")
        payload={"evidence_id":evidence.evidence_id,"evidence_hash":evidence.original_page_sha256,
                 "description":description,"model_run_id":model_run_id}
        signature=sha(canonical(payload))
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing=conn.execute("SELECT * FROM drafts WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                if existing["payload_hash"]!=signature:
                    raise ValueError("idempotency_key_collision_with_different_payload")
                return existing["draft_id"]
            draft_id=str(uuid.uuid4())
            conn.execute("""INSERT INTO drafts
                (draft_id,idempotency_key,evidence_id,evidence_sha256,description,payload_hash,state,created_at)
                VALUES(?,?,?,?,?,?,'DRAFT',?)""",
                (draft_id,idempotency_key,evidence.evidence_id,evidence.original_page_sha256,
                 description,signature,utc()))
            self._audit(conn,draft_id,"DRAFT_CREATED","AI_PLANNER_TEST",{
                "evidence_id":evidence.evidence_id,"evidence_sha256":evidence.original_page_sha256,
                "source_model_run_id":model_run_id})
            return draft_id

    def issue_owner_challenge(self,draft_id:str)->str:
        """Only the disconnected owner-operator CLI may invoke this method.
        No HTTP route exposes it and the AI tool set never receives it.
        """
        secret=secrets.token_urlsafe(24)
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row=conn.execute("SELECT state FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
            if row is None or row["state"]!="DRAFT":
                raise ValueError("challenge_requires_pending_draft")
            conn.execute("UPDATE drafts SET approval_secret_hash=? WHERE draft_id=?",
                         (sha(secret),draft_id))
            self._audit(conn,draft_id,"OWNER_CHALLENGE_ISSUED","OWNER_OPERATOR_CHANNEL",
                        {"secret_disclosed_in_audit":False})
        return secret

    def approve(self,draft_id:str,reviewer:str,secret:str,principal:str|None=None)->None:
        if reviewer not in AUTHORIZED_ROLES:
            raise PermissionError("reviewer_role_not_allowed")
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row=conn.execute("SELECT state,approval_secret_hash FROM drafts WHERE draft_id=?",
                             (draft_id,)).fetchone()
            if not row or row["state"]!="DRAFT":
                raise ValueError("approval_requires_pending_draft")
            if not row["approval_secret_hash"] or not secrets.compare_digest(row["approval_secret_hash"],sha(secret)):
                self._audit(conn,draft_id,"APPROVAL_REJECTED","OWNER_OPERATOR_CHANNEL",
                            {"reason":"invalid_or_missing_challenge"})
                raise_token=True
            else:
                actor=principal or reviewer
                if not isinstance(actor,str) or not actor.strip() or len(actor)>100:
                    raise ValueError("invalid_approver_identity")
                conn.execute("UPDATE drafts SET state='APPROVED',approved_by=?,approval_secret_hash=NULL WHERE draft_id=?",
                             (actor,draft_id))
                self._audit(conn,draft_id,"HUMAN_APPROVED",actor,{"confirmed":True,"role":reviewer})
                raise_token=False
        if raise_token:
            raise PermissionError("approval_challenge_invalid")

    def reject(self,draft_id:str,principal:str,reason:str="EDITORIAL_NOT_ACCEPTED")->str:
        """Record an owner's explicit refusal without any task or model action."""
        if not isinstance(principal,str) or not 1<=len(principal)<=100:
            raise ValueError("invalid_owner_rejection_identity")
        if reason not in {"EDITORIAL_NOT_ACCEPTED","BUSINESS_NOT_RELEVANT",
                          "INSUFFICIENT_EVIDENCE","OTHER"}:
            raise ValueError("invalid_rejection_reason")
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row=conn.execute("SELECT state FROM drafts WHERE draft_id=?",(draft_id,)).fetchone()
            if row is None:raise ValueError("reject_draft_not_found")
            if row["state"]=="REJECTED":return "REJECTED"
            if row["state"]!="DRAFT":raise ValueError("only_pending_draft_can_be_rejected")
            task=conn.execute("SELECT 1 FROM tasks WHERE draft_id=?",(draft_id,)).fetchone()
            if task is not None:raise RuntimeError("rejected_draft_cannot_have_task")
            conn.execute("UPDATE drafts SET state='REJECTED',approval_secret_hash=NULL WHERE draft_id=?",
                         (draft_id,))
            self._audit(conn,draft_id,"HUMAN_REJECTED",principal,
                        {"reason":reason,"external_action":False,"task_created":False})
        return "REJECTED"

    def execute(self,draft_id:str,inject_failure:bool=False)->str:
        """Only inserts an internal test task, never an external action."""
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row=conn.execute("SELECT * FROM drafts WHERE draft_id=?",(draft_id,)).fetchone()
            if not row:raise ValueError("draft_not_found")
            if row["state"]=="EXECUTED":
                task=conn.execute("SELECT task_id FROM tasks WHERE draft_id=?",(draft_id,)).fetchone()
                if not task:raise RuntimeError("executed_draft_without_task")
                return task["task_id"]
            if row["state"]!="APPROVED" or not row["approved_by"]:
                self._audit(conn,draft_id,"EXECUTION_DENIED","INTERNAL_ACTION_RUNNER",
                            {"reason":"approval_missing"})
                denied=True
            else:denied=False
            if denied:
                # persist denied attempts as audit, without creating task
                task_id=None
            elif inject_failure:
                self._audit(conn,draft_id,"EXECUTION_TEST_FAILURE","INTERNAL_ACTION_RUNNER",
                            {"reason":"injected_failure_no_task_created"})
                task_id=None
            else:
                task_id=str(uuid.uuid4())
                conn.execute("INSERT INTO tasks(task_id,draft_id,description,evidence_id,created_at) VALUES(?,?,?,?,?)",
                             (task_id,draft_id,row["description"],row["evidence_id"],utc()))
                conn.execute("UPDATE drafts SET state='EXECUTED' WHERE draft_id=?",(draft_id,))
                self._audit(conn,draft_id,"INTERNAL_TASK_EXECUTED","INTERNAL_ACTION_RUNNER",
                            {"task_id":task_id,"external_action":False})
        if denied:raise PermissionError("human_approval_required")
        if inject_failure:raise RuntimeError("injected_execution_failure")
        return task_id

    def verify_audit(self)->dict:
        with self.db() as conn:
            events=conn.execute("SELECT * FROM audit ORDER BY sequence").fetchall()
            prev="0"*64
            for row in events:
                rec={"timestamp":row["timestamp"],"draft_id":row["draft_id"],
                     "event":row["event"],"actor":row["actor"],
                     "metadata":json.loads(row["metadata"]),"prev":prev}
                if row["prev_sha256"]!=prev or row["hash_sha256"]!=sha(canonical(rec)):
                    raise RuntimeError("audit_integrity_failed")
                prev=row["hash_sha256"]
            tasks=conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"]
            return {"audit_events":len(events),"internal_tasks":tasks,
                    "integrity":"CHAIN_VERIFIED","external_actions":0}
