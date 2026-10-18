"""LOCAL owner-only visual QA checklist for decrypted real RASD Word reports.

No network, mail, scheduler, key upload, or public publisher material.
Never change the original signed/encrypted package or infer human review.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from docx import Document
from PIL import Image

WORD_MODE = "stage2_ministry_unified_word_ephemeral_qa"
EXPECTED_SOURCES = {"hapi", "almasryalyoum", "mped-official"}
CAIRO = ZoneInfo("Africa/Cairo")


def _json_file(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("private_review_file_missing_or_symlink")
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError("private_review_json_invalid")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_private_review(folder: Path, day: date) -> dict:
    """Validate actual local-decrypted contents, NEVER use public CI samples."""
    if type(day) is not date:
        raise ValueError("review_expected_day_invalid")
    # Local human attestation is only meaningful for an already completed
    # Cairo day; never bless the current partial day or a future report.
    if day >= datetime.now(CAIRO).date():
        raise ValueError("private_review_incomplete_cairo_calendar_day")
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("private_review_folder_invalid")
    audit = _json_file(folder / "rasd-owner-review-audit.json")
    if (audit.get("mode") != WORD_MODE or
            audit.get("target_date_cairo") != day.isoformat() or
            audit.get("status") != "READY_QA_ONLY" or
            audit.get("all_sources_healthy") is not True or
            audit.get("word_created") is not True or
            audit.get("word_images_verified") is not True or
            audit.get("official_pagination_complete") is not True or
            audit.get("private_renderer_passed") is not True or
            audit.get("human_visual_review") is not False or
            audit.get("production_delivery_approved") is not False or
            audit.get("owner_review_word_included") is not True or
            audit.get("owner_review_pages_encrypted") is not True or
            audit.get("email_sent") is not False or
            audit.get("scheduler_enabled") is not False or
            audit.get("source_added_to_production") is not False):
        raise ValueError("private_review_audit_not_qualified")
    sources = audit.get("source_health")
    if (not isinstance(sources, list) or len(sources) != 3 or
            {row.get("feed_id") for row in sources if type(row) is dict}
            != EXPECTED_SOURCES or
            any(type(row) is not dict or row.get("status") != "ok" or
                type(row.get("verified_links")) is not int or
                row["verified_links"] < 0 or
                (row.get("feed_id") == "mped-official" and
                 row["verified_links"] < 1) for row in sources)):
        raise ValueError("private_review_original_sources_not_healthy")
    count = audit.get("selected_unique_articles")
    if (type(count) is not int or not 1 <= count <= 15 or
            audit.get("screenshots_verified") != count or
            audit.get("screenshots_missing") != 0):
        raise ValueError("private_review_article_evidence_missing")
    word = folder / f"RASD-Unified-{day.isoformat()}.docx"
    if not word.is_file() or word.is_symlink() or word.stat().st_size < 3000:
        raise ValueError("private_review_word_missing")
    if (len(list(folder.glob("RASD-Unified-*.docx"))) != 1 or
            len(Document(word).inline_shapes) != count):
        raise ValueError("private_review_word_image_count_mismatch")
    manifest = _json_file(folder / "rasd-owner-review-pages-manifest.json")
    pages = manifest.get("pages")
    if (manifest.get("version") != 1 or
            not isinstance(pages, list) or
            not 1 <= len(pages) <= max(3, count * 4 + 3) or
            audit.get("owner_review_page_count") != len(pages)):
        raise ValueError("private_review_pages_manifest_invalid")
    root = folder / "review-pages"
    if not root.is_dir() or root.is_symlink():
        raise ValueError("private_review_pages_folder_invalid")
    actual = sorted(root.iterdir())
    if len(actual) != len(pages):
        raise ValueError("private_review_page_list_mismatch")
    hashes = []
    for idx, row in enumerate(pages, 1):
        expected = f"review-pages/page-{idx:03d}.png"
        target = root / f"page-{idx:03d}.png"
        if (type(row) is not dict or row.get("name") != expected or
                not target.is_file() or target.is_symlink() or
                actual[idx-1] != target or
                type(row.get("bytes")) is not int or
                row["bytes"] != target.stat().st_size or
                not isinstance(row.get("sha256"), str) or
                not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) or
                _digest(target) != row["sha256"]):
            raise ValueError("private_review_page_integrity_mismatch")
        with Image.open(target) as picture:
            if (picture.format != "PNG" or picture.width < 550 or
                    picture.height < 550):
                raise ValueError("private_review_page_geometry_invalid")
            picture.verify()
        hashes.append(row["sha256"])
    return {
        "target_date_cairo": day.isoformat(),
        "original_source_count": 3,
        "article_count": count,
        "review_page_count": len(pages),
        "word_sha256": _digest(word),
        "page_sha256": hashes,
        "local_integrity_checked": True,
        "human_visual_review": False,
        "production_delivery_approved": False,
    }


def make_private_gallery(folder: Path, details: dict) -> Path:
    """A purely local HTML viewer; no script, CDN, network or external links."""
    folder = Path(folder)
    day = details["target_date_cairo"]
    total = details["review_page_count"]
    sections = []
    for number in range(1, total + 1):
        img = f"review-pages/page-{number:03d}.png"
        sections.append(
            f'<section><h2>صفحة {number} من {total}</h2>'
            f'<img src="{img}" alt="صفحة {number} من التقرير" loading="lazy"></section>'
        )
    word = f"RASD-Unified-{day}.docx"
    markup = (
        '<!doctype html><html lang="ar" dir="rtl"><head>'
        '<meta charset="utf-8"><title>رصد — مراجعة محلية فقط</title>'
        '<style>body{font:16px system-ui;max-width:1000px;margin:auto;'
        'padding:22px;background:#f6f6f6;color:#182b32}'
        'section{background:white;margin:28px 0;padding:18px;'
        'box-shadow:0 2px 8px #bbb}img{display:block;max-width:100%;'
        'height:auto;margin:auto}a{color:#086a80}</style></head><body>'
        f'<h1>رصد — مراجعة تقرير {html.escape(day)}</h1>'
        '<p><b>نسخة محلية خاصة.</b> افحص كل صفحة، اتجاه العربية، المصدر '
        'والتاريخ، الصورة الأصلية، قص الأطراف والصفحات البيضاء. '
        'نجاح فحص سلامة الملفات لا يعني موافقة بشرية ولا إذنًا بالإرسال.</p>'
        f'<p>عدد الأخبار {details["article_count"]} — عدد الصفحات {total}</p>'
        f'<p><a href="{html.escape(word)}">فتح Word الأصلي محليًا</a></p>'
        + "".join(sections) + "</body></html>"
    )
    destination = folder / "rasd-private-review-index.html"
    if destination.is_symlink():
        raise ValueError("private_review_gallery_symlink_forbidden")
    destination.write_text(markup, encoding="utf-8")
    return destination


def owner_local_attestation(folder: Path, details: dict) -> Path:
    """One explicit TTY owner decision; never machine-approve a page."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("owner_visual_attestation_requires_local_tty")
    day = details["target_date_cairo"]
    pages = details["review_page_count"]
    token = f"REVIEWED {day} {pages}"
    print(f"Open the PRIVATE local gallery. Check ALL {pages} real pages and the Word.")
    print("This attests YOUR visual review only; it does NOT authorize delivery.")
    if input(f"Type {token} exactly after reviewing every page: ").strip() != token:
        raise ValueError("owner_visual_review_not_confirmed")
    output = Path(folder) / "rasd-owner-human-review-attestation.json"
    if output.exists() or output.is_symlink():
        raise ValueError("owner_visual_attestation_existing_no_overwrite")
    receipt = {
        "type": "RASD_LOCAL_OWNER_SELF_ATTESTED_REVIEW_V1",
        "target_date_cairo": day,
        "word_sha256": details["word_sha256"],
        "page_sha256": details["page_sha256"],
        "review_page_count": pages,
        "reviewed_at_cairo": datetime.now(CAIRO).isoformat(),
        "human_visual_review": True,
        "production_delivery_approved": False,
        "verification_note": "Local human self-attestation, not a digital signature",
    }
    # Permission 0600 where available; do not overwrite/replace existing receipts.
    import os
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True,
                        help="Local folder produced by the existing owner-only decrypt tool")
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--attest", action="store_true",
                        help="Require explicit local interactive human confirmation")
    args = parser.parse_args()
    details = inspect_private_review(args.folder, args.day)
    gallery = make_private_gallery(args.folder, details)
    if args.attest:
        owner_local_attestation(args.folder, details)
        status = "LOCAL_HUMAN_SELF_ATTESTATION_RECORDED_NOT_DELIVERY_APPROVAL"
    else:
        status = "READY_FOR_PRIVATE_HUMAN_VISUAL_REVIEW_NOT_APPROVED"
    print(json.dumps({
        "status": status, "day": details["target_date_cairo"],
        "review_pages": details["review_page_count"],
        "gallery_file": str(gallery),
        "production_delivery_approved": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
