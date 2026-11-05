"""Read-only GitHub-hosted preflight of PRIVATE QA settings. NO SMTP or ledger writes.

Designed to run only in a protected Github environment. Prints only bounded
validation status, not recipient/secret/source data. Missing credential => HOLD.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import ssl
from pathlib import Path
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from rasd_settings_bridge_qa import validate_owner_settings, _hash

REPO="Hatem1984/RASD-Pilot"
REF="rasd-private-delivery-state"
PATH="settings/rasd-owner-qa-active.json"
URL=f"https://api.github.com/repos/{REPO}/contents/{PATH}?ref={REF}"
BASELINE=Path(__file__).with_name("sources_owner_daily_qa.json")
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("unexpected_redirect")

def run(*, token=None, opener=None):
    token=os.environ.get("RASD_PRIVATE_LEDGER_TOKEN","") if token is None else token
    if not isinstance(token,str) or len(token)<16:
        raise RuntimeError("protected_private_reader_unavailable")
    request=Request(URL,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"RASD-owner-QA-readonly",
    })
    opener=opener or build_opener(NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(request,timeout=14) as response:
        raw=response.read(70_001)
    if len(raw)>70_000:
        raise RuntimeError("protected_manifest_size_hold")
    envelope=json.loads(raw.decode("utf-8"))
    if envelope.get("encoding")!="base64" or envelope.get("type")!="file":
        raise RuntimeError("protected_manifest_envelope_hold")
    manifest=json.loads(base64.b64decode(envelope["content"]).decode("utf-8"))
    if (manifest.get("scope")!="QA_PREVIEW_NO_SEND"
            or manifest.get("schema_version")!=1
            or not isinstance(manifest.get("active_version"),int)):
        raise RuntimeError("protected_qa_scope_hold")
    settings=manifest["settings"]
    if any(word in key.lower() for key in settings for word in
           ("secret","token","recipient","password","email","smtp")):
        raise RuntimeError("sensitive_setting_field_hold")
    if manifest.get("sha256")!=_hash(settings):
        raise RuntimeError("protected_manifest_digest_hold")
    baseline=json.loads(BASELINE.read_text(encoding="utf-8"))
    validate_owner_settings(settings,baseline)
    return {"qa_only":True,"send_allowed":False,"sources":len(settings["sources"]),
            "topics":len(settings["topics"]),"active_version":manifest["active_version"],
            "manifest_hash_confirmed":True}
if __name__=="__main__":
    try:
        result=run()
    except Exception:
        # Never print untrusted HTTP responses or secrets in public logs.
        print("RASD_PROTECTED_PRIVATE_READONLY=HOLD",flush=True)
        raise SystemExit(2)
    print("RASD_PROTECTED_PRIVATE_READONLY=PASS")
    print("RASD_NO_SEND=true")
    print("RASD_ACTIVE_QA_VERSION="+str(result["active_version"]))
    print("RASD_SOURCE_COUNT="+str(result["sources"]))
