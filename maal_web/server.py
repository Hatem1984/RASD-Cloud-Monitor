"""MA'AL local competition-preview read-only gateway.

Strict localhost bind, allowlisted paths, no cloud writes, no auth claims.
Original evidence is supplied exclusively by an owner-local Gate E receipt and
is rechecked against the screenshot SHA256 before being served.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import io
from zipfile import ZipFile, BadZipFile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date, datetime

HERE = Path(__file__).resolve().parent
# Import the existing Gate D contract from this same integration branch.
sys.path.insert(0, str(HERE.parent))
from maal.decision_contracts import Evidence
PROJECT = next((folder for folder in HERE.parents if folder.name.upper() == "MAAL"), None)
if PROJECT is None:
    raise RuntimeError("MAAL_ROOT_NOT_FOUND")
RASD = PROJECT / "01_ACTIVE_CODE" / "RASD-Cloud-Monitor"
BRAND = PROJECT / "MAAL_Approved_Brand_Kit_2026" / "MAAL_Brand_Kit_2026" / "logo_references"
CASE_DIR = PROJECT / "03_REPORTS_AND_REVIEW" / "MAAL_GATE_E_ACCEPTANCE_20261026"
CASE_JSON = CASE_DIR / "MAAL-historical-signal-demo.json"
CASE_IMAGE = CASE_DIR / "official-original.jpg"
CASE_REPORT = CASE_DIR / "MAAL-historical-signal-demo.docx"
STATIC = {
    "/": (HERE / "index.html", "text/html; charset=utf-8"),
    "/style.css": (HERE / "style.css", "text/css; charset=utf-8"),
    "/app.js": (HERE / "app.js", "text/javascript; charset=utf-8"),
    "/brand-symbol.png": (BRAND / "logo_mono_ivory_transparent.png", "image/png"),
    "/brand-logo.png": (BRAND / "logo_primary_reference.png", "image/png"),
}

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
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        try:
            if path == "/api/snapshot":
                return self.reply(200, "application/json; charset=utf-8",
                                  json.dumps(get_snapshot(), ensure_ascii=False).encode("utf-8"))
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
        self.reply(405, "application/json; charset=utf-8", b'{"error":"read_only_preview"}')

    def reply(self, status: int, mime: str, body: bytes,
              filename: str | None = None) -> None:
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
