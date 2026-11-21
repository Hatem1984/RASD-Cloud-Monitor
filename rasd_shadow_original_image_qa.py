"""Bounded ORIGINAL publisher article photo QA for three Nov-20 sources.

Research only. Fixed first-party URLs, no secrets, SMTP, private ledger,
production activation, browser access bypass, or public photo artifacts.
Publisher refusal or a missing lead image is recorded as HOLD.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from capture_public import APPROVED_PUBLISHERS, allowed_url, capture_publisher
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "rasd_shadow_originals_20261120.json"


def qa_candidates(capture=capture_publisher, cases: list[dict] | None = None) -> dict:
    inventory = json.loads((ROOT / "sources_newsroom_active.json").read_text("utf-8"))
    production_ids = {row["id"] for row in inventory["feeds"]}
    source = json.loads(FIXTURES.read_text(encoding="utf-8"))
    checked = source["cases"] if cases is None else cases
    if not isinstance(checked, list) or not 1 <= len(checked) <= 5:
        raise ValueError("shadow_source_count_hold")
    reports = []
    with tempfile.TemporaryDirectory(prefix="rasd-candidate-firstparty-") as directory:
        for row in checked:
            ident, base, url = row["id"], row["base"], row["url"]
            hosts = row["hosts"]
            if ((ident in production_ids and ident != "alnaharegypt")
                    or (base in APPROVED_PUBLISHERS and ident != "alnaharegypt")
                    or not isinstance(hosts, list) or len(hosts) != 1
                    or not isinstance(url, str) or
                    not url.startswith("https://") or
                    base not in {"alnaharegypt.com", "youm7.com",
                                 "ahram.org.eg", "almalnews.com",
                                 "almasdar.com"}):
                raise RuntimeError("shadow_publisher_unapproved_identity_hold")
            with patch.dict(APPROVED_PUBLISHERS, {base: frozenset(hosts)}):
                if not allowed_url(url, base):
                    raise RuntimeError("shadow_original_url_invalid")
                image = Path(directory) / (ident + ".jpg")
                result = capture(url, base, image)
                if result.get("ok") is True:
                    receipt = result.get("sha256")
                    if (not isinstance(receipt, str)
                            or receipt != hashlib.sha256(image.read_bytes()).hexdigest()
                            or result.get("actual_url") != url):
                        raise RuntimeError("shadow_original_identity_digest_hold")
                    reports.append({"id": ident,
                                    "status": "ORIGINAL_PAGE_IMAGE_QA_PASS",
                                    "photo_sha256_verified": True,
                                    "production_approved": False})
                else:
                    reason = result.get("reason")
                    if reason not in SAFE_CAPTURE_FAILURE_CODES:
                        reason = "other"
                    reports.append({"id": ident, "status": "ORIGINAL_PAGE_IMAGE_HOLD",
                                    "reason": reason,
                                    "photo_sha256_verified": False,
                                    "production_approved": False})
    return {"scope": "RESEARCH_ONLY_NO_SEND",
            "checked": len(reports),
            "passed": sum(r["photo_sha256_verified"] for r in reports),
            "production_activated": 0, "smtp_sent": False,
            "stories": reports}


def main():
    report=qa_candidates()
    # Do not expose raw page contents, URL querystrings, original images or
    # exception text in this public test-only job.
    print("RASD_CANDIDATE_ORIGINALS_CHECKED=" + str(report["checked"]))
    print("RASD_CANDIDATE_ORIGINALS_PASSED=" + str(report["passed"]))
    for row in report["stories"]:
        print("RASD_CANDIDATE_ID=" + row["id"] +
              " IMAGE_STATUS=" + row["status"] +
              (" HOLD_REASON=" + row["reason"] if row.get("reason") else ""))
    print("RASD_NO_PRODUCTION_SOURCE_ACTIVATION=1 SMTP=0")


if __name__=="__main__":
    main()
