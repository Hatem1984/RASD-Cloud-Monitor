"""Opt-in read-only replay of one already reviewed Ministry article (2026-10-17).
Evidence stays in the operator's local QA directory; no outbound mail.
"""
import argparse
import json
from datetime import date
from pathlib import Path

from maal.decision_contracts import BusinessContext
from maal.impact_mvp import BusinessDemoProfile, interpret_official_signal, write_demo_docx
from official_ministry_source import SAMPLE, _read_original, allowed_official_resource


def main(destination: Path) -> dict:
    repo = Path(__file__).resolve().parents[1]
    target = destination.resolve()
    if repo == target or repo in target.parents:
        raise ValueError("original_publisher_evidence_must_stay_outside_public_git")
    target.mkdir(parents=True, exist_ok=True)
    config = json.loads((repo / "sources.json").read_text(encoding="utf-8"))
    if config.get("keywords") != [
        "وزارة التخطيط", "وزير التخطيط",
        "وزيرة التخطيط", "التخطيط والتنمية الاقتصادية"]:
        raise ValueError("approved_source_profile_drift")
    picture = target / "official-original.jpg"
    docx = target / "MAAL-historical-signal-demo.docx"
    brief = target / "MAAL-historical-signal-demo.json"
    if any(file.exists() for file in (picture, docx, brief)):
        raise ValueError("refuse_overwrite_existing_original_proof")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 900}, locale="ar-EG",
                service_workers="block", ignore_https_errors=False)
            context.route("**/*", lambda request: (
                request.continue_() if allowed_official_resource(request.request.url)
                else request.abort()))
            page = context.new_page()
            receipt = _read_original(
                page, SAMPLE, config["keywords"], date(2026, 10, 17), picture)
            if receipt.get("status") != "verified":
                return {"status": "HOLD_NO_DEMO",
                        "reason": receipt.get("reason", "unknown"),
                        "email_sent": False, "ledger_changed": False}
            profile = BusinessDemoProfile(
                BusinessContext(
                    "SYNTHETIC-EGYPT-INFRA-SME",
                    "شركة افتراضية تعمل في الطاقة المتجددة والبنية التحتية",
                    "مصر"),
                ("infrastructure_finance", "renewable_energy"))
            body = page.locator("body").inner_text(timeout=8000)
            answer = interpret_official_signal(receipt, body, picture, profile)
            write_demo_docx(answer, picture, docx)
            brief.write_text(
                json.dumps(answer, ensure_ascii=False, indent=2),
                encoding="utf-8")
            return {"status": "HISTORICAL_VERIFIED_DEMO",
                    "source_date_only": "2026-10-17",
                    "original_screenshot_verified": True,
                    "docx_original_image_sha_match": True,
                    "brief": str(brief), "word": str(docx),
                    "email_sent": False, "ledger_changed": False}
        finally:
            browser.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(main(args.output_dir), ensure_ascii=False, indent=2))
