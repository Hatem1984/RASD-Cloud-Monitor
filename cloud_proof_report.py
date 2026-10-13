"""Cloud-native, screenshot-required public news report builder (manual preview).

The program runs on the hosted worker and never needs an owner's Windows PC.
It produces a final report only if EVERY selected article has a validated,
original-publisher browser screenshot. No original photo substitutes for it.
No Gmail, schedule, bypass or private delivery state is involved.
"""
from __future__ import annotations

import base64
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from capture_public import APPROVED_PUBLISHERS, allowed_url, capture_publisher, image_quality
from daily_report import gather, render_docx, render_pdf
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES
from monitor import article_id, canonical_url, read_feed


def classify_failure(reason: str | None) -> str:
    """Never print untrusted server replies or exception text in public logs."""
    return reason if isinstance(reason, str) and reason in SAFE_CAPTURE_FAILURE_CODES else "other"


def proof_capture(article: dict, feeds: list[dict], destination: Path,
                  *, capture=capture_publisher) -> dict:
    """Enforce URL provenance, article/title identity and actual JPEG integrity."""
    feed = next((x for x in feeds if x["name"] == article["source"]), None)
    publisher = next(
        (name for name in APPROVED_PUBLISHERS if allowed_url(article["url"], name)),
        None,
    )
    if (not feed or not publisher or
            urlsplit(article["url"]).hostname not in feed["allowed_article_hosts"] or
            not allowed_url(article["url"], publisher) or
            article_id(article["url"]) != article["id"]):
        return {"status": "hold", "reason": "source_identity_mismatch"}
    result = capture(article["url"], publisher, destination)
    if not result.get("ok"):
        return {"status": "hold", "reason": classify_failure(result.get("reason"))}
    if (not result.get("actual_url") or
            canonical_url(result["actual_url"]) != canonical_url(article["url"])):
        return {"status": "hold", "reason": "url_mismatch"}
    if article["headline"].strip()[:12] not in result.get("title", ""):
        return {"status": "hold", "reason": "title_mismatch"}
    if not destination.is_file() or destination.stat().st_size < 8000:
        return {"status": "hold", "reason": "screenshot_too_small"}
    quality = image_quality(destination)
    if not quality["accepted"]:
        return {"status": "hold", "reason": classify_failure("visual_qa_" + quality["reason"])}
    raw = destination.read_bytes()
    if not raw.startswith(b"\xff\xd8"):
        return {"status": "hold", "reason": "invalid_jpeg_signature"}
    digest = hashlib.sha256(raw).hexdigest()
    if result.get("sha256") and digest != result["sha256"]:
        return {"status": "hold", "reason": "screenshot_digest_mismatch"}
    return {"status": "verified", "sha256": digest, "bytes": len(raw)}


def build_proof_report(config_path: Path, output_dir: Path, *, fetch=read_feed,
                       capture=capture_publisher, now: datetime | None = None) -> dict:
    """Fail-closed for final Word/PDF; produce a redacted audit manifest on HOLD."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    report = gather(config, fetch=fetch, now=now)
    output_dir.mkdir(parents=True, exist_ok=True)
    day = report["window_end_cairo"][:10]
    manifest_path = output_dir / f"RASD-Proof-{day}-manifest.json"
    rows = []
    with tempfile.TemporaryDirectory(prefix="rasd-proofs-") as tmp:
        for article in report["articles"]:
            destination = Path(tmp) / (article["id"] + ".jpg")
            result = proof_capture(article, config["feeds"], destination, capture=capture)
            rows.append({"id": article["id"], "source": article["source"], **result})
            if result["status"] == "verified":
                article["evidence_image_path"] = str(destination)
                article["evidence_image_base64"] = base64.b64encode(
                    destination.read_bytes()
                ).decode("ascii")
        verified = sum(row["status"] == "verified" for row in rows)
        ready = (bool(rows) and verified == len(rows)
                 and report["coverage"] == "HEALTHY")
        result = {
            "mode": "cloud_manual_publisher_screenshot_required",
            "status": "READY" if ready else "HOLD",
            "articles": len(rows), "screenshots_verified": verified,
            "screenshots_missing": len(rows) - verified,
            "coverage": report["coverage"],
            "entries": rows,
            "email_sent": False, "scheduler_enabled": False,
            "owner_pc_required": False,
        }
        if ready:
            # Both files must render before either becomes a final artifact.
            # A blocked publisher produces only the HOLD manifest.
            prefix = f"RASD-Proof-{day}"
            with tempfile.TemporaryDirectory(prefix=".rasd-docs-", dir=output_dir) as work:
                word = Path(work) / (prefix + ".docx")
                pdf = Path(work) / (prefix + ".pdf")
                render_docx(report, word)
                render_pdf(report, pdf)
                if not word.is_file() or not pdf.is_file():
                    raise RuntimeError("publisher_proof_document_missing")
                word.replace(output_dir / word.name)
                pdf.replace(output_dir / pdf.name)
        manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("proof-output"))
    opts = parser.parse_args()
    try:
        result = build_proof_report(Path("sources.json"), opts.output_dir)
        print(json.dumps({key: val for key, val in result.items() if key != "entries"},
                         ensure_ascii=False), flush=True)
        if result["status"] != "READY":
            print("::warning::Screenshot-required report ON HOLD; approved publisher-page evidence missing",
                  flush=True)
            raise SystemExit(2)
    except SystemExit:
        raise
    except Exception:
        print("rasd_proof_report_failed_closed", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
