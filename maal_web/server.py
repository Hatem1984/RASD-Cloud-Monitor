"""MA'AL local competition-preview read-only gateway.

Strict localhost bind, allowlisted paths, no cloud writes, no auth claims.
Original evidence is supplied exclusively by an owner-local Gate E receipt and
is rechecked against the screenshot SHA256 before being served.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import io
from zipfile import ZipFile, BadZipFile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date, datetime
from http.cookies import SimpleCookie
from secrets import compare_digest

HERE = Path(__file__).resolve().parent
# Import the existing Gate D contract from this same integration branch.
sys.path.insert(0, str(HERE.parent))
from maal.decision_contracts import Evidence
from maal.operator_gateway import OperatorGateway
from maal.competition_journey import assemble_agent_journey
from maal.report_bundle_guard import inspect_bundle
PROJECT = next((folder for folder in HERE.parents if folder.name.upper() == "MAAL"), None)
if PROJECT is None:
    raise RuntimeError("MAAL_ROOT_NOT_FOUND")
RASD = PROJECT / "01_ACTIVE_CODE" / "RASD-Cloud-Monitor"
BRAND = PROJECT / "MAAL_Approved_Brand_Kit_2026" / "MAAL_Brand_Kit_2026" / "logo_references"
CASE_DIR = PROJECT / "03_REPORTS_AND_REVIEW" / "MAAL_GATE_E_ACCEPTANCE_20261026"
CASE_JSON = CASE_DIR / "MAAL-historical-signal-demo.json"
CASE_IMAGE = CASE_DIR / "official-original.jpg"
CASE_REPORT = CASE_DIR / "MAAL-historical-signal-demo.docx"
MODEL_RUN=PROJECT/"04_HISTORICAL_QA"/"MAAL_COMPETITION_MVP_20261028"/"fresh_model_run.json"
# Isolated demo state, NOT a Gmail/private-ledger database.
OP_DB=PROJECT/"04_HISTORICAL_QA"/"MAAL_GATE_H_E2E_20261027"/"operator.sqlite"
_GATEWAY=None
def gateway():
    global _GATEWAY
    if _GATEWAY is None: _GATEWAY=OperatorGateway(OP_DB)
    return _GATEWAY

STATIC = {
    "/": (HERE / "index.html", "text/html; charset=utf-8"),
    "/style.css": (HERE / "style.css", "text/css; charset=utf-8"),
    "/app.js": (HERE / "app.js", "text/javascript; charset=utf-8"),
    "/operator.js": (HERE / "operator.js", "text/javascript; charset=utf-8"),
    "/agent-journey.js": (HERE / "agent-journey.js", "text/javascript; charset=utf-8"),
    "/new-signals.js": (HERE / "new-signals.js", "text/javascript; charset=utf-8"),
    "/business-value-study.js": (HERE / "business-value-study.js", "text/javascript; charset=utf-8"),
    "/product_report.json": (HERE / "product_report.json", "application/json; charset=utf-8"),
    # Explicitly named local owner-review files, not a dynamic user-provided path.
    "/reports/MAAL_Business_Intelligence_Round2_2026-10-27.pdf":
       (PROJECT/"03_REPORTS_AND_REVIEW"/"MAAL_PRODUCT_ACCEPTANCE_R2_20261027"/"owner_downloads"/
        "MAAL_Business_Intelligence_Round2_2026-10-27.pdf", "application/pdf"),
    "/reports/MAAL_Business_Intelligence_Round2_2026-10-27.docx":
       (PROJECT/"03_REPORTS_AND_REVIEW"/"MAAL_PRODUCT_ACCEPTANCE_R2_20261027"/"owner_downloads"/
        "MAAL_Business_Intelligence_Round2_2026-10-27.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "/brand-symbol.png": (BRAND / "logo_mono_ivory_transparent.png", "image/png"),
    "/brand-logo.png": (BRAND / "logo_primary_reference.png", "image/png"),
}

STAGED_REVIEW = PROJECT / "04_HISTORICAL_QA" / "MAAL_UNIFIED_SNAPSHOT_REVIEW_20261027" / "current.json"
BUNDLE_MANIFEST = PROJECT / "04_HISTORICAL_QA" / "MAAL_BUNDLE_PARITY_20261027" / "approved_bundle_manifest.json"
PRODUCT_REPORT_URLS = {
    "pdf": "/reports/MAAL_Business_Intelligence_Round2_2026-10-27.pdf",
    "docx": "/reports/MAAL_Business_Intelligence_Round2_2026-10-27.docx",
}
def verified_product_bundle() -> tuple[dict, dict[str,bytes]]:
    """Hash-bound historical snapshot and owner-reviewed artifact bytes only.

    The bundled files are static, prior owner-reviewed reports: they do NOT
    auto-regenerate on new UI metadata. A changed revision/fact/file fails.
    """
    snapshot = get_safe_staging_report()
    manifest = json.loads(BUNDLE_MANIFEST.read_text("utf8"))
    binaries = {ext: STATIC[url][0].read_bytes() for ext,url in PRODUCT_REPORT_URLS.items()}
    return inspect_bundle(snapshot=snapshot,manifest=manifest,files=binaries), binaries


def get_safe_staging_report() -> dict:
    """QA-only file reads; never trust caller paths or call RASD production."""
    original = json.loads((HERE / "product_report.json").read_text("utf8"))
    candidate = json.loads(STAGED_REVIEW.read_text("utf8"))
    meta = candidate.pop("snapshot_meta", None)
    if not isinstance(meta, dict) or meta.get("kind") != "HISTORICAL_READONLY_QA":
        raise ValueError("invalid_snapshot_kind")
    if candidate != original:
        raise ValueError("snapshot_source_changed_without_approved_evidence")
    if (meta.get("source_new_verified_news_count") != 0 or
            meta.get("source_live_connected") is not False or
            meta.get("no_email_sent") is not True):
        raise ValueError("unverified_freshness_claim")
    if meta.get("original_gate_e_sha256") != get_case()["evidence_digest"]:
        raise ValueError("gate_e_original_sha256_mismatch")
    candidate["snapshot_meta"] = meta
    return candidate

def get_snapshot() -> dict:
    """Snapshot not live coverage; never claim feeds are healthy."""
    active = json.loads((RASD / "sources_newsroom_active.json").read_text("utf-8"))
    researched = json.loads((RASD / "research_sources_top50.json").read_text("utf-8"))
    feeds = active["feeds"]
    if not isinstance(feeds, list) or not isinstance(active["keywords"], list):
        raise ValueError("Invalid source configuration")
    sources = []
    for row in feeds:
        domain = urlsplit(row["url"]).hostname or ""
        if not domain or not row.get("id") or not row.get("name"):
            raise ValueError("Malformed feed")
        parsed = urlsplit(row["url"])
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Invalid feed URL")
        safe_hosts = row.get("allowed_article_hosts")
        if not isinstance(safe_hosts, list) or not all(
                isinstance(h, str) and h for h in safe_hosts):
            raise ValueError("Missing approved host policy")
        sources.append({"id": row["id"], "name": row["name"], "domain": domain,
                        "feed_url": row["url"],
                        "allowed_article_hosts": safe_hosts,
                        "scope": "configured", "health": "NOT_LIVE_CHECKED"})
    return {
        "as_of": "2026-10-26", "mode": "LOCAL_PREVIEW", "live": False,
        "active_feeds": len(feeds), "keywords": len(active["keywords"]),
        "research_sources": len(researched["sources"]),
        "sources": sources, "snapshot_notice": "إعدادات مؤرخة، لا تحقق لحظي من حالة المصادر",
        "production_writes": False,
    }

def get_case() -> dict:
    raw = json.loads(CASE_JSON.read_text("utf-8"))
    if (raw.get("status") != "DRAFT_REQUIRES_HUMAN_APPROVAL"
            or raw.get("sample_company_is_synthetic") is not True
            or raw.get("decision_contract_validated") is not True
            or raw.get("external_actions_executed") is not False
            or raw.get("email_sent") is not False):
        raise ValueError("Unapproved demo receipt")
    evidence = raw["evidence"]
    url = evidence["url"]
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "mped.gov.eg"
            or parsed.path != "/singlenews" or
            url != "https://mped.gov.eg/singlenews?id=7269&lang=ar"):
        raise ValueError("Wrong original publisher")
    if evidence.get("published_day_cairo") != "2026-10-17" or evidence.get("published_time") is not None:
        raise ValueError("Publication precision altered")
    expected = evidence["original_page_jpeg_sha256"]
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Invalid SHA256")
    # Enforce the shared Gate D evidence contract, not a second invented schema.
    validated_evidence = Evidence(
        evidence_id=evidence["evidence_id"],
        publisher=evidence["publisher"],
        original_url=url,
        claim=evidence["finding"],
        published_at=date.fromisoformat(evidence["published_day_cairo"]),
        observed_at=datetime.fromisoformat(evidence["observed_at"]),
        original_page_sha256=expected,
        status="VERIFIED_ORIGINAL_PAGE",
    )
    validated_evidence.validate()
    if not raw["facts_from_verified_inputs"] or (
        raw["facts_from_verified_inputs"][0]["evidence_id"]
        != validated_evidence.evidence_id
    ):
        raise ValueError("Gate D evidence identity mismatch")
    # Validate source binary before any image or demo datum leaves the local server.
    file_hash = hashlib.sha256(CASE_IMAGE.read_bytes()).hexdigest()
    if file_hash != expected:
        raise ValueError("Original screenshot digest mismatch")
    return {
        "record_type": "HISTORICAL_VERIFIED_DEMO",
        "evidence_id": validated_evidence.evidence_id,
        "verification_status": validated_evidence.status,
        "timeliness": "HISTORICAL",
        "inference_type": "RULE_BASED_CONDITIONAL",
        "producer": "RASD_VERIFIED_ORIGINAL_GATE_E",
        "verified_receipt": True, "synthetic_company": True,
        "headline": evidence["headline"], "published_day": "2026-10-17",
        "observed_at": evidence["observed_at"],
        "publication_precision": "DATE_ONLY",
        "publisher": evidence["publisher"], "original_url": url,
        "evidence_digest": expected, "evidence_image_url": "/api/case-image",
        "finding": evidence["finding"],
        "sector": raw["business_context"]["sector"],
        "market": raw["business_context"]["market"],
        "hypothesis": raw["business_impact"]["hypothesis"],
        "unknowns": raw["business_impact"]["not_established"],
        "proposals": [
            {"kind": item["action_type"], "description": item["description"],
             "evidence_ids": item["supporting_evidence_ids"]}
            for item in raw["proposals_not_executed"]
        ],
        "limitations": raw["limitations"],
        "actions_enabled": False, "email_sent": False, "confidence_score": None,
        "financial_impact": None,
    }

def get_local_ai_run() -> dict:
    """Owner-local actual llama.cpp result; explicitly not an approved decision."""
    case=get_case()
    raw=json.loads(MODEL_RUN.read_text("utf8"))
    analysis=raw.get("analysis")
    from maal.ai_decision_engine import ALLOWED_DECISION_OPTIONS, ALLOWED_IMPACT_HYPOTHESES, ALLOWED_UNKNOWNS
    if (raw.get("accepted_by_contract") is not True or
        raw.get("real_local_inference") is not True or
        not isinstance(raw.get("run_id"),str) or not raw["run_id"].startswith("maal-g3-") or
        raw.get("model") != "Qwen3-1.7B-Q4_K_M" or
        raw.get("evidence_id")!=case["evidence_id"] or
        raw.get("original_digest")!=case["evidence_digest"] or
        not isinstance(analysis,dict) or
        analysis.get("status")!="AI_DRAFT_UNREVIEWED" or
        analysis.get("verified_evidence_ids")!=[case["evidence_id"]] or
        analysis.get("action_executed") is not False or
        analysis.get("human_approval_required") is not True or
        analysis.get("recommendation_draft") not in ALLOWED_DECISION_OPTIONS or
        analysis.get("inference") not in ALLOWED_IMPACT_HYPOTHESES or
        not isinstance(analysis.get("unknowns"),list) or
        not analysis["unknowns"] or not set(analysis["unknowns"]).issubset(ALLOWED_UNKNOWNS) or
        analysis.get("facts_exact_from_evidence") != [case["finding"]] or
        not isinstance(analysis.get("alternatives"),list) or
        not set(analysis["alternatives"]).issubset(ALLOWED_DECISION_OPTIONS)):
        raise ValueError("local_model_result_not_authorized_to_display")
    return {
        "model":raw["model"],"backend":"local_cpu_llama_cpp",
        "run_id":raw["run_id"],"recorded_at":raw["timestamp_utc"],
        "inference_seconds":raw["inference_seconds"],
        "cloud_api_cost_usd":0.0,"published_as_real_time":False,
        "source_id":case["evidence_id"],
        "source_url":case["original_url"],
        "source_sha256":case["evidence_digest"],
        "record_type":"ACTUAL_MODEL_OUTPUT_AWAITING_HUMAN_REVIEW",
        "quality_approval":"HOLD_HUMAN_REVIEW",
        "status":analysis["status"],
        "facts":analysis["facts_exact_from_evidence"],
        "inference":analysis["inference"],
        "unknowns":analysis["unknowns"],
        "alternatives":analysis["alternatives"],
        "recommendation":analysis["recommendation_draft"],
        "actions_executed":False,
    }


def get_verified_report_bytes() -> bytes:
    """Serve an existing approved Word specimen only if the original image is present."""
    case = get_case()
    data = CASE_REPORT.read_bytes()
    try:
        with ZipFile(io.BytesIO(data), "r") as doc:
            media = [name for name in doc.namelist()
                     if name.startswith("word/media/") and not name.endswith("/")]
            if len(media) != 1:
                raise ValueError("Unexpected number of Word evidence images")
            digest = hashlib.sha256(doc.read(media[0])).hexdigest()
            if digest != case["evidence_digest"]:
                raise ValueError("Word image integrity mismatch")
    except BadZipFile as error:
        raise ValueError("Invalid Word document") from error
    return data


class Handler(BaseHTTPRequestHandler):
    def _cookie(self):
        header=self.headers.get("Cookie","")
        if len(header)>2100:return ""
        try:
            cookies=SimpleCookie();cookies.load(header)
            return cookies["maal_demo"].value if "maal_demo" in cookies else ""
        except Exception:return ""

    def _json_response(self,code:int,data:dict,extra=None):
        return self.reply(code,"application/json; charset=utf-8",
                          json.dumps(data,ensure_ascii=False).encode("utf-8"),extra_headers=extra)

    def _evidence_for_draft(self):
        item=get_case()
        return Evidence(
            evidence_id=item["evidence_id"],publisher=item["publisher"],
            original_url=item["original_url"],claim=item["finding"],
            published_at=date.fromisoformat(item["published_day"]),
            observed_at=datetime.fromisoformat(item["observed_at"]),
            original_page_sha256=item["evidence_digest"],
            status=item["verification_status"]
        )

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        try:
            if path == "/api/operator/state":
                try:return self._json_response(200,gateway().dashboard(self._cookie()))
                except PermissionError:return self._json_response(401,{"error":"login_required"})
            if path == "/product_report.json" and os.environ.get("MAAL_HISTORICAL_SNAPSHOT_REVIEW") == "true":
                return self._json_response(200,get_safe_staging_report())
            if path == "/api/report-bundle":
                if os.environ.get("MAAL_HISTORICAL_SNAPSHOT_REVIEW") != "true":
                    return self._json_response(403,{"error":"historical_review_disabled"})
                result, _ = verified_product_bundle()
                return self._json_response(200,result)
            if path in PRODUCT_REPORT_URLS.values():
                if os.environ.get("MAAL_HISTORICAL_SNAPSHOT_REVIEW") != "true":
                    return self._json_response(403,{"error":"historical_review_disabled"})
                _, verified_files = verified_product_bundle()
                ext = next(ext for ext, url in PRODUCT_REPORT_URLS.items() if url==path)
                asset, mime = STATIC[path]
                return self.reply(200,mime,verified_files[ext],
                    filename=asset.name)
            if path == "/api/snapshot":
                return self.reply(200, "application/json; charset=utf-8",
                                  json.dumps(get_snapshot(), ensure_ascii=False).encode("utf-8"))
            if path == "/api/agent-journey":
                # All visible claims derive from one unchanged original and
                # one persisted, independently checked local model receipt.
                who = None
                try:
                    who = gateway().dashboard(self._cookie())
                except PermissionError:
                    pass
                case=get_case()
                ai=get_local_ai_run()
                journey=assemble_agent_journey(case,ai,who)
                try:
                    from maal.competition_report_bundle import read_bound_bundle
                    manifest,_=read_bound_bundle(case,ai,MODEL_RUN.parent/"reports")
                    journey["report"].update({
                        "status":"SOURCE_LINKED_QWEN_WORD_PDF_QA",
                        "ai_run_bound_word_pdf_available":True,
                        "docx_url":"/api/agent-report.docx",
                        "pdf_url":"/api/agent-report.pdf",
                        "manifest_sha256_report":manifest["docx_sha256"],
                    })
                except (OSError,ValueError,KeyError):
                    pass  # Never represent a stale/incomplete bundle as ready.
                return self._json_response(200,journey)
            if path in ("/api/agent-report.docx","/api/agent-report.pdf"):
                # Pin both download bytes to the current original and model.
                from maal.competition_report_bundle import read_bound_bundle
                _,bundle=read_bound_bundle(get_case(),get_local_ai_run(),MODEL_RUN.parent/"reports")
                kind="pdf" if path.endswith(".pdf") else "docx"
                mime=("application/pdf" if kind=="pdf" else
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                return self.reply(200,mime,bundle[kind],
                    filename="MAAL-Source-Linked-Qwen-Review."+kind)
            if path == "/api/competition-demo.webm":
                from hashlib import sha256
                root=Path("E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_COMPETITION_MVP_20261028/new_source_demo")
                manifest=json.loads((root/"walkthrough_acceptance.json").read_text("utf8"))
                if (manifest.get("status")!="CONTINUOUS_OWNER_REVIEW_DEMO_PASS" or
                    manifest.get("new_approval_performed") is not False or
                    manifest.get("new_task_executed") is not False or
                    manifest.get("video_scope")!="SAVED_REAL_QWEN_INFERENCE_REPLAYED_FROM_VERIFIED_RECEIPT__NO_LIVE_INFERENCE_IN_TAPE"):
                    raise ValueError("demo_acceptance_provenance_hold")
                video=Path(manifest["video_path"]).resolve()
                expected_dir=(root/"continuous_readonly_video").resolve()
                if video.parent!=expected_dir or video.suffix.lower()!=".webm":
                    raise ValueError("demo_path_not_authorized")
                binary=video.read_bytes()
                if (not 100000<=len(binary)<=150000000 or
                    sha256(binary).hexdigest()!=manifest["video_sha256"]):
                    raise ValueError("demo_integrity_hold")
                return self.reply(200,"video/webm",binary,
                      filename="MAAL_Real_Source_Qwen_to_Human_Review_ONLY.webm")
            if path == "/api/new-signals":
                from maal.competition_new_source import verified_cases
                from maal.competition_new_reasoning import verified_runs, COMPANY
                captured=verified_cases()
                runs=verified_runs()
                # Private editorial review is independent from JSON schema
                # validity and the owner approval ledger. Missing = HOLD.
                editorial_path=Path("E:/MAAL/04_HISTORICAL_QA/MAAL_COMPETITION_MVP_20261028/editorial_quality_20261028.json")
                try:
                    editorial=json.loads(editorial_path.read_text("utf8"))
                    if editorial.get("schema")!="MAAL_EDITORIAL_REVIEW_V1":
                        raise ValueError("untrusted_editorial_review_schema")
                    assessments=editorial["cases"]
                except (OSError,ValueError,KeyError,TypeError):
                    assessments={}
                owner_drafts=[]
                try:
                    owner_drafts=gateway().dashboard(self._cookie())["drafts"]
                except PermissionError:
                    pass
                entries=[]
                for item in captured:
                    selected=next((r for r in runs if r["evidence_id"]==item["evidence_id"]),None)
                    entries.append({
                        "case":{
                            k:item[k] for k in ("evidence_id","publisher","headline",
                                "original_url","published_day","date_precision",
                                "observed_at","verification_status","evidence_digest",
                                "evidence_image_url","sector_angle","proof_method","source_key")
                        },
                        "ai":None if not selected else {
                            k:selected[k] for k in ("run_id","status","model",
                                "elapsed_seconds","token_usage","analysis","error",
                                "recorded_at","evidence_id")
                        },
                        "editorial_review": (
                            assessments[item["evidence_id"]]
                            if selected and
                               assessments.get(item["evidence_id"],{}).get("run_id")==selected["run_id"]
                            else {"status":"HOLD","reason":"لم تُعتمد المراجعة التحريرية لهذا التشغيل."}
                        ),
                        "owner_draft":next(({
                            "draft_id":d["draft_id"],
                            "state":d["state"],
                            "task_id":d.get("task_id")
                        } for d in owner_drafts if
                            d["evidence_id"]==item["evidence_id"]),None)
                    })
                return self._json_response(200,{
                    "schema":"MAAL_NEW_OFFICIAL_SIGNALS_V1",
                    "scope":"OWNER_LOCAL_OFFICIAL_SOURCE_CAPTURE",
                    "live_schedule":False,"company":COMPANY,
                    "items":entries,"approval_requires_human":True})
            if path.startswith("/api/new-signal/image/"):
                from maal.competition_new_source import ROOT,get_case_from_capture
                import re
                ident=path.rsplit("/",1)[-1]
                if not re.fullmatch(r"[0-9a-f]{24}",ident):
                    return self._json_response(404,{"error":"invalid_source_id"})
                record=get_case_from_capture(ROOT/ident)
                return self.reply(200,"image/jpeg",(ROOT/ident/"publisher-page.jpeg").read_bytes())
            if path == "/api/ai-analysis":
                return self._json_response(200,get_local_ai_run())
            if path == "/api/evidence":
                item = get_case()
                data = {
                    "schema": "MAAL_EVIDENCE_LIST_V1",
                    "as_of": "2026-10-27",
                    "mode": "OWNER_LOCAL_READ_ONLY",
                    "items": [{
                        "evidence_id": item["evidence_id"],
                        "status": item["verification_status"],
                        "timeliness": item["timeliness"],
                        "published_day": item["published_day"],
                        "publication_precision": item["publication_precision"],
                        "observed_at": item["observed_at"],
                        "original_url": item["original_url"],
                        "original_sha256": item["evidence_digest"],
                        "publisher": item["publisher"],
                        "headline": item["headline"],
                        "inference_type": item["inference_type"],
                        "financial_impact": None,
                    }],
                    "live_feed_connection": False,
                    "private_ledger_exposed": False,
                }
                return self.reply(200, "application/json; charset=utf-8",
                                  json.dumps(data,ensure_ascii=False).encode("utf-8"))
            if path == "/api/case":
                return self.reply(200, "application/json; charset=utf-8",
                                  json.dumps(get_case(), ensure_ascii=False).encode("utf-8"))
            if path == "/api/case-image":
                get_case()  # always verify the owner-only SHA256 and publisher identity
                return self.reply(200, "image/jpeg", CASE_IMAGE.read_bytes())
            if path == "/api/case-report":
                return self.reply(200,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    get_verified_report_bytes(),
                    filename="MAAL-verified-historical-case.docx")
            if path in STATIC:
                asset, mime = STATIC[path]
                return self.reply(200, mime, asset.read_bytes())
            return self.reply(404, "application/json; charset=utf-8",
                              b'{"error":"not_found"}')
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self.reply(503, "application/json; charset=utf-8",
                              b'{"error":"verified_data_unavailable"}')

    def do_POST(self) -> None:
        path=urlsplit(self.path).path
        actions={
            "/api/operator/login","/api/operator/logout",
            "/api/operator/draft","/api/operator/approve","/api/operator/reject","/api/operator/execute",
            "/api/operator/editorial-signoff",
            "/api/ai/run"
        }
        if path not in actions:
            return self._json_response(405,{"error":"read_only_preview"})
        # Dedicated localhost test-only route. Explicit same-origin checks and CSRF.
        port=self.server.server_address[1]
        expected=f"http://127.0.0.1:{port}"
        if self.headers.get("Origin")!=expected or (
            self.headers.get("Content-Type","").split(";")[0]!="application/json"
        ):
            return self._json_response(403,{"error":"invalid_origin_or_content_type"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 1<=length<=4096: return self._json_response(413,{"error":"invalid_body_size"})
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError("invalid_payload")
            gate=gateway()
            if path=="/api/operator/login":
                token,csrf=gate.login(body.get("login",""),body.get("password",""))
                return self._json_response(200,{"authenticated":True,"csrf":csrf},
                    extra={"Set-Cookie":f"maal_demo={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200"})
            token=self._cookie()
            csrf=self.headers.get("X-CSRF-Token","")
            actor=gate.require(token,csrf)
            if path=="/api/operator/logout":
                gate.logout(token)
                return self._json_response(200,{"logged_out":True},
                    extra={"Set-Cookie":"maal_demo=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
            if path=="/api/ai/run":
                if actor["role"]!="OWNER":
                    raise PermissionError("owner_only_real_ai")
                if body.get("intent")!="fresh_historical_demo_only":
                    raise ValueError("invalid_ai_run_intent")
                from maal.demo_runtime import infer_to_local_receipt
                result=infer_to_local_receipt(get_case(),MODEL_RUN)
                return self._json_response(200,{"run":result,"analysis":get_local_ai_run()})
            if path=="/api/operator/editorial-signoff":
                from maal.competition_editorial_gate import sign_owner_editorial
                result=sign_owner_editorial(gate,token,csrf,body.get("model_run_id"),
                                             body.get("stepup_password",""))
                return self._json_response(200,result)
            if path=="/api/operator/draft":
                linked_run=body.get("model_run_id")
                fresh_evidence=body.get("new_evidence_id")
                evidence=self._evidence_for_draft()
                if fresh_evidence is not None:
                    from maal.competition_new_source import ROOT,get_case_from_capture
                    from maal.competition_new_reasoning import verified_runs
                    import re
                    if (not isinstance(fresh_evidence,str) or
                            not re.fullmatch(r"[0-9a-f]{24}",fresh_evidence)):
                        raise ValueError("new_evidence_invalid")
                    # ONE GENERAL immutable editorial gate for ANY source or
                    # draft. No run-specific/hardcoded FPT exception exists.
                    from maal.competition_editorial_gate import check_run_binding
                    case,verified_run,description=check_run_binding(gate.store,linked_run,actor)
                    if (case["evidence_id"]!=fresh_evidence or
                        body.get("description")!=description):
                        raise ValueError("model_evidence_or_action_contract_hold")
                    evidence=Evidence(case["evidence_id"],case["publisher"],
                        case["original_url"],case["headline"],
                        date.fromisoformat(case["published_day"]) if case["published_day"]
                           else datetime.fromisoformat(case["observed_at"]).date(),
                        datetime.fromisoformat(case["observed_at"]),
                        case["evidence_digest"],case["verification_status"])
                else:
                    # Historical unbound owner drafts remain readable, but may
                    # NOT be created/approved by this competition endpoint.
                    raise ValueError("new_draft_requires_evidence_and_editorial_signoff")
                result=gate.create(token,csrf,evidence,
                                   body.get("description",""),body.get("idempotency_key",""),
                                   model_run_id=linked_run)
                return self._json_response(200,{"draft_id":result,"state":"DRAFT",
                  "evidence_id":evidence.evidence_id,"source_model_run_id":linked_run})
            if path=="/api/operator/approve":
                from maal.competition_editorial_gate import require_draft_allowed
                require_draft_allowed(gate,actor,body.get("draft_id",""))
                result=gate.approve(token,csrf,body.get("draft_id",""),
                                    body.get("stepup_password",""))
                return self._json_response(200,result)
            if path=="/api/operator/reject":
                result=gate.reject(token,csrf,body.get("draft_id",""),
                                   body.get("stepup_password",""),
                                   body.get("reason","EDITORIAL_NOT_ACCEPTED"))
                return self._json_response(200,result)
            if path=="/api/operator/execute":
                from maal.competition_editorial_gate import require_draft_allowed
                require_draft_allowed(gate,actor,body.get("draft_id",""))
                result=gate.execute(token,csrf,body.get("draft_id",""))
                return self._json_response(200,result)
        except PermissionError:
            return self._json_response(403,{"error":"authentication_or_authorization_required"})
        except (ValueError,TypeError,KeyError):
            return self._json_response(400,{"error":"invalid_or_unverified_request"})
        except (OSError,RuntimeError):
            return self._json_response(503,{"error":"local_test_action_unavailable"})
        return self._json_response(404,{"error":"not_found"})

    def reply(self, status: int, mime: str, body: bytes,
              filename: str | None = None, extra_headers:dict|None=None) -> None:
        self.send_response(status)
        headers = {
            "Content-Type": mime, "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self'; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"),
        }
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        if extra_headers:
            headers.update(extra_headers)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return  # do not log original publisher article data

def serve(port: int = 52318) -> None:
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"MAAL_V03_LOCAL_READY http://127.0.0.1:{port}/", flush=True)
        server.serve_forever()

if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 52318)
