"""RASD QA settings bridge: active version -> scan configuration, strictly read-only.

An owner web draft is NEVER a production configuration. Cloud deployment must
later fetch the same validated active manifest from a protected private store.
Only ordinary settings appear here; no recipients or credentials are exported.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from monitor import _ministry_term_present
from rasd_halfhour_policy_qa import matched_owner_topics

KEYS = ("topics","sources","start","end","report_title","report_type",
        "detail","analysis_instructions","include","scan_minutes","send_mode","send_at")
VERSION=1
def _hash(s: dict) -> str:
    return hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False,
           separators=(",",":")).encode("utf-8")).hexdigest()

def validate_owner_settings(settings:dict,baseline:dict)->None:
    if not isinstance(settings,dict):raise ValueError("settings_invalid")
    if any(k not in settings for k in KEYS):raise ValueError("settings_missing_required")
    if settings["scan_minutes"]!=30 or settings["send_mode"]!="daily" or settings["send_at"]!="22:00":
        raise ValueError("unreviewed_schedule_not_allowed")
    if not isinstance(settings["start"],str) or not isinstance(settings["end"],str):
        raise ValueError("cairo_window_invalid")
    if (any(not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]",settings[k]) for k in ("start","end"))
        or not ("00:00"<=settings["start"]<settings["end"]<="23:59")):
        raise ValueError("same_cairo_day_required")
    if not isinstance(settings["topics"],list) or len(settings["topics"])>45:
        raise ValueError("invalid_owner_topic_groups")
    for topic in settings["topics"]:
        if (topic.get("match") not in ("any","all") or
            type(topic.get("enabled")) is not bool or
            not isinstance(topic.get("aliases"),list) or
            not 1<=len(topic["aliases"])<=10 or
            any(not isinstance(s,str) or not 2<=len(s)<=100 for s in topic["aliases"])):
            raise ValueError("invalid_owner_topic")
    approved={f["id"]:f for f in baseline["feeds"]}
    listed=settings["sources"]
    if (not isinstance(listed,list) or len(listed)!=len(approved)
        or {s.get("id") for s in listed}!=set(approved)):
        raise ValueError("approved_source_inventory_mismatch")
    for row in listed:
        origin=approved[row["id"]]
        if (row.get("name")!=origin["name"] or row.get("url")!=origin["url"]
                or type(row.get("enabled")) is not bool):
            raise ValueError("approved_source_tampered")
    proposals=settings.get("source_proposals",[])
    if not isinstance(proposals,list) or len(proposals)>20:
        raise ValueError("unreviewed_source_proposals_invalid")
    for p in proposals:
        if not isinstance(p,dict) or p.get("status")!="PENDING_REVIEW":
            raise ValueError("source_proposal_must_remain_pending")
    if not any(s["enabled"] for s in listed):
        raise ValueError("all_sources_disabled")
    if not isinstance(settings["include"],dict) or any(
        settings["include"].get(k) is not True for k in ("headlines","links","screenshots")
    ):raise ValueError("mandatory_evidence_elements_removed")

def active_snapshot_from_db(dbfile:Path,baseline:dict)->dict:
    if not dbfile.is_file():raise RuntimeError("owner_active_store_missing_hold")
    # No writes, no database creation, never silently select 'draft'.
    c=sqlite3.connect(f"file:{dbfile.as_posix()}?mode=ro",uri=True)
    try:
        row=c.execute("SELECT version,payload FROM settings WHERE slot='active'").fetchone()
    finally:c.close()
    if not row:raise RuntimeError("owner_active_settings_missing_hold")
    version,payload=row
    settings=json.loads(payload)
    validate_owner_settings(settings,baseline)
    safe={k:settings[k] for k in KEYS}
    return {"schema_version":VERSION,"active_version":version,"settings":safe,
            "sha256":_hash(safe),"scope":"QA_PREVIEW_NO_SEND"}

def scanned_config(snapshot:dict,baseline:dict)->dict:
    if snapshot.get("schema_version")!=VERSION or snapshot.get("scope") not in ("QA_PREVIEW_NO_SEND","ACTIVE_APPROVED"):
        raise ValueError("untrusted_owner_snapshot")
    safe=snapshot["settings"]
    if _hash(safe)!=snapshot.get("sha256"):
        raise ValueError("owner_snapshot_digest_mismatch")
    validate_owner_settings(safe,baseline)
    active_ids={s["id"] for s in safe["sources"] if s["enabled"]}
    active_topics=[t for t in safe["topics"] if t["enabled"]]
    if not active_topics:raise ValueError("all_topics_disabled_hold")
    keywords=list(dict.fromkeys(alias for t in active_topics for alias in t["aliases"]))
    if not keywords:raise ValueError("owner_scan_without_keywords")
    feeds=[f for f in baseline["feeds"] if f["id"] in active_ids]
    return {**baseline,"feeds":feeds,"keywords":keywords}

def filter_owner_topic_matches(articles:list[dict],settings:dict)->list[dict]:
    """Existing monitor RSS matching is a broad first pass (OR).
    Then enforce the owner's per-topic any/all exact grouping on true
    publisher title/excerpt. Prevent draft words from leaking into processing.
    """
    return [r for r in articles if matched_owner_topics(r,settings)]

def verify_cloud_ready_manifest(manifest:dict,baseline:dict)->dict:
    """Validates same contract expected by a future private GitHub/Cloudflare
    store, never decides to send or retrieves any secret.
    """
    if manifest.get("scope")!="ACTIVE_APPROVED":
        raise ValueError("nonactive_cloud_settings_refused")
    if manifest.get("schema_version")!=VERSION:
        raise ValueError("cloud_settings_schema_mismatch")
    if not isinstance(manifest.get("active_version"),int) or manifest["active_version"]<1:
        raise ValueError("cloud_active_version_missing")
    if _hash(manifest.get("settings",{}))!=manifest.get("sha256"):
        raise ValueError("cloud_settings_digest_mismatch")
    validate_owner_settings(manifest["settings"],baseline)
    return manifest
