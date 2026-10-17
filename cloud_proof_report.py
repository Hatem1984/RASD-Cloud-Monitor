"""Cloud-native, screenshot-required public news report builder (manual preview).

The program runs on the hosted worker and never needs an owner's Windows PC.
It produces a final report only if EVERY selected article has a validated,
original-publisher browser screenshot. No original photo substitutes for it.
No Gmail, schedule, bypass or private delivery state is involved.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from capture_public import APPROVED_PUBLISHERS, allowed_url, capture_publisher, image_quality
from daily_report import gather, render_docx
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES
from monitor import article_id, canonical_url, read_feed



def word_images_match_capture_digests(word: Path, entries: list[dict]) -> bool:
    """Check the DOCX actually *displays* each independently captured JPEG.

    ZIP media presence alone is insufficient: every Word drawing must resolve
    to exactly one internal image relationship and the exact captured SHA-256.
    No browser, network, secret, mailer, or private ledger is involved.
    """
    captured = [row.get("sha256") for row in entries
                if row.get("status") == "verified"]
    if (not captured or len(captured) != len(entries) or
            any(not isinstance(value, str) or len(value) != 64
                for value in captured)):
        return False
    try:
        with zipfile.ZipFile(word) as archive:
            if archive.testzip() is not None:
                return False
            rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
            document = ET.fromstring(archive.read("word/document.xml"))
            rel_by_id = {}
            for rel in rels:
                if not rel.attrib.get("Type", "").endswith("/image"):
                    continue
                target = rel.attrib.get("Target", "")
                if (not target.startswith("media/") or
                        "/" in target[len("media/"):] or
                        not target.lower().endswith((".jpg", ".jpeg"))):
                    return False
                rel_by_id[rel.attrib["Id"]] = "word/" + target
            embed_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            blip_tag = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
            embeds = [node.attrib.get(embed_key) for node in document.iter(blip_tag)]
            if not embeds or len(embeds) != len(captured):
                return False
            targets = [rel_by_id.get(reference) for reference in embeds]
            if any(target is None for target in targets):
                return False
            # No unused embedded media and no repeated picture standing in
            # for distinct publisher-article evidence.
            media = {name for name in archive.namelist()
                     if name.startswith("word/media/") and not name.endswith("/")}
            if len(targets) != len(set(targets)) or media != set(targets):
                return False
            observed = sorted(hashlib.sha256(archive.read(name)).hexdigest()
                              for name in targets)
            return observed == sorted(captured)
    except (OSError, KeyError, ValueError, TypeError, zipfile.BadZipFile, ET.ParseError):
        return False


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
                       capture=capture_publisher, now: datetime | None = None,
                       archive_writer=None) -> dict:
    """Fail-closed for final Word; produce a redacted audit manifest on HOLD."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    report = gather(config, fetch=fetch, now=now)
    # The Shorouk-only qualification profile is not the production-wide
    # daily scope: print the boundary in the Word itself, not just Actions.
    if ([x["id"] for x in config["feeds"]] == ["shorouk"]):
        report["title"] = "رصد | تقرير مراجعة مصدر الشروق — صور ناشر موثقة"
        report["limitations"] += (
            " هذا اختبار نطاق مصدر الشروق الاختياري وحده؛"
            " لا يشهد على اكتمال الرصد اليومي لجميع المصادر."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    day = report["window_end_cairo"][:10]
    manifest_path = output_dir / f"RASD-Proof-{day}-manifest.json"
    # A failed second attempt must not expose a prior same-day final DOCX.
    # This destination is a temporary build area; archival copies live elsewhere.
    (output_dir / f"RASD-Daily-{day}.docx").unlink(missing_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix="rasd-proofs-") as tmp:
        for article in report["articles"]:
            destination = Path(tmp) / (article["id"] + ".jpg")
            result = proof_capture(article, config["feeds"], destination, capture=capture)
            rows.append({"id": article["id"], "source": article["source"], **result})
            if result["status"] == "verified":
                article["evidence_image_path"] = str(destination)
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
            "private_state_used": False, "owner_pc_required": False,
        }
        if ready:
            filename = f"RASD-Daily-{day}.docx"
            destination = output_dir / filename
            with tempfile.TemporaryDirectory(prefix=".rasd-word-", dir=output_dir) as work:
                word = Path(work) / filename
                render_docx(report, word)
                valid_word = (
                    word.is_file()
                    and word.stat().st_size >= 3000
                    and word_images_match_capture_digests(word, rows)
                )
                if valid_word:
                    word.replace(destination)
            if not valid_word:
                # A visually plausible document with wrong/unused/missing
                # media is NOT a final source-backed report.
                result["status"] = "HOLD"
                result["word_created"] = False
                result["archive_status"] = "NOT_ATTEMPTED"
                result["failure"] = "word_evidence_integrity_failed"
            else:
                result["word_created"] = True
                result["archive_status"] = "NOT_CONFIGURED"
                if archive_writer is not None:
                    # Only exact, capture-verified Word bytes may enter the
                    # private archive; a bad receipt fails closed.
                    evidence = [(row["id"], Path(tmp) / (row["id"] + ".jpg"),
                                 row["sha256"]) for row in rows]
                    try:
                        receipt = archive_writer.publish_ready(
                            report=result, word=destination, evidence=evidence)
                        if (receipt.get("status") != "PRIVATE_VERIFIED" or
                                receipt.get("screenshots_archived") != len(rows) or
                                receipt.get("word_archived") is not True):
                            raise RuntimeError("private_archive_receipt_invalid")
                    except Exception:
                        destination.unlink(missing_ok=True)
                        result["status"] = "HOLD"
                        result["word_created"] = False
                        result["archive_status"] = "FAILED"
                    else:
                        result["archive_status"] = "PRIVATE_VERIFIED"
                        result["archive_manifest_sha256"] = receipt["manifest_sha256"]
        else:
            result["word_created"] = False
            result["archive_status"] = "NOT_ATTEMPTED"
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
