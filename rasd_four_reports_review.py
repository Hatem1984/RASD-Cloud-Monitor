"""Four independent RASD Word report REVIEW contracts.

Reference: user-supplied ministry web (1 Nov) and social (7 Nov) PDF layouts.
No SMTP, GitHub private CAS access, schedule, API keys, or Meta/browser IO.
A future authenticated adapter must supply source-verified, image-bound
receipts. This module alone does not prove Facebook post authenticity.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from PIL import Image
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from daily_report import _rtl, _word_hyperlink

CAIRO = ZoneInfo("Africa/Cairo")
CHANNELS = {"web": "المواقع الإلكترونية", "social": "شبكات التواصل الاجتماعي"}
PLATFORMS = {
    "facebook": {"facebook.com", "www.facebook.com", "m.facebook.com"},
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "linkedin": {"linkedin.com", "www.linkedin.com"},
}
STATE_LABELS = {
    "ok": "متاح", "hold": "معلّق — يلزم مراجعة",
    "unavailable": "غير متاح", "unauthorized": "تصريح الوصول غير متوفر",
    "not_configured": "غير معتمد بعد",
}
MAX_ROWS = 250
MAX_IMAGE_BYTES = 8_000_000
MAX_WORD_BYTES = 50_000_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAIL_ID = re.compile(r"<rasd-[0-9a-f]{24}@gmail\.com>\Z")
_BAD_QUERY = {"access_token", "token", "password", "cookie", "code",
              "appsecret_proof", "session", "auth_token"}


def _clock(value: str | datetime) -> datetime:
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone_required_hold")
    return dt.astimezone(timezone.utc)


def _url(url: str, channel: str, platform: str | None,
         allowed_hosts: set[str] | None = None) -> str:
    if not isinstance(url, str) or len(url) > 1800:
        raise ValueError("article_url_hold")
    try:
        p = urlsplit(url)
        if (p.scheme != "https" or not p.hostname or p.port not in (None, 443)
                or p.username or p.password or p.fragment or not p.path.strip("/")
                or any(ord(c) < 32 for c in url)):
            raise ValueError("article_url_hold")
        if any(x.split("=", 1)[0].lower() in _BAD_QUERY
               for x in p.query.split("&") if x):
            raise ValueError("article_url_secret_hold")
        host = p.hostname.lower()
        if channel == "social":
            if platform not in PLATFORMS or host not in PLATFORMS[platform]:
                raise ValueError("social_platform_identity_hold")
            path = p.path.rstrip("/")
            if platform == "facebook" and not (
                    "/posts/" in path or path.endswith("/story.php")
                    or "/reel/" in path):
                raise ValueError("social_post_permalink_hold")
            if platform == "x" and "/status/" not in path:
                raise ValueError("social_post_permalink_hold")
            if platform == "instagram" and not (
                    "/p/" in path or "/reel/" in path):
                raise ValueError("social_post_permalink_hold")
            if platform == "linkedin" and not (
                    "/posts/" in path or "/feed/update/" in path):
                raise ValueError("social_post_permalink_hold")
        elif channel == "web":
            if not allowed_hosts or host not in allowed_hosts:
                raise ValueError("unapproved_news_host_hold")
        else:
            raise ValueError("channel_invalid")
        return url
    except (ValueError, TypeError):
        raise ValueError("article_url_or_platform_hold") from None


def _image(path: str, digest: str, evidence_root: Path) -> Path:
    if not isinstance(path, str) or not _SHA.fullmatch(str(digest)):
        raise ValueError("evidence_receipt_hold")
    p = Path(path).resolve(strict=True)
    base = evidence_root.resolve(strict=True)
    if not p.is_relative_to(base) or p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("evidence_path_outside_review_root")
    raw = p.read_bytes()
    if (not 100 <= len(raw) <= MAX_IMAGE_BYTES
            or hashlib.sha256(raw).hexdigest() != digest):
        raise ValueError("evidence_hash_mismatch_hold")
    with Image.open(p) as picture:
        if (picture.format not in {"JPEG", "PNG"}
                or picture.width < 50 or picture.height < 50
                or picture.width > 14000 or picture.height > 14000):
            raise ValueError("evidence_image_invalid")
        picture.verify()
    return p


def validate_item(item: dict, channel: str, evidence_root: Path,
                  allowed_web_hosts: set[str], *, cutoff: datetime) -> dict:
    """Verify only technical provenance; original-page truth is a separate gate."""
    if not isinstance(item, dict) or item.get("channel") != channel:
        raise ValueError("wrong_channel_hold")
    name = item.get("source")
    title = item.get("title")
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 160
            or not isinstance(title, str) or not 1 <= len(title.strip()) <= 300):
        raise ValueError("missing_publisher_or_title_hold")
    url = _url(item.get("url"), channel, item.get("platform"),
               allowed_web_hosts if channel == "web" else None)
    timestamp = _clock(item.get("published_at"))
    if timestamp > cutoff:
        raise ValueError("future_dated_source_hold")
    # An independently authorized original-page verifier is still required.
    receipt = item.get("capture_receipt")
    if (not isinstance(receipt, dict)
            or receipt.get("status") != "verified"
            or receipt.get("url") != url
            or receipt.get("sha256") != item.get("image_sha256")
            or receipt.get("method") not in
               ({"approved_web_publisher_capture"} if channel == "web"
                else {"authorized_platform_original_capture"})):
        raise ValueError("original_page_capture_receipt_hold")
    image_path = _image(item.get("image_path"), item.get("image_sha256"),
                        evidence_root)
    ident = hashlib.sha256(
        (channel + ":" + url.split("#", 1)[0]).encode("utf-8")).hexdigest()
    if item.get("id") not in (None, ident):
        raise ValueError("story_identity_mismatch_hold")
    return {**item, "id": ident, "image_path": str(image_path),
            "_when": timestamp, "_verified": True}


def _states(rows: list[dict], channel: str) -> list[dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("source_status_required_hold")
    checked, seen = [], set()
    for row in rows:
        if (not isinstance(row, dict)
                or row.get("channel") != channel
                or row.get("status") not in STATE_LABELS
                or not isinstance(row.get("name"), str)
                or not row["name"].strip()):
            raise ValueError("invalid_source_status_hold")
        if row["name"] in seen:
            raise ValueError("duplicate_source_status_hold")
        seen.add(row["name"])
        checked.append({"name": row["name"], "status": row["status"]})
    return checked


def _unique(rows: list[dict]) -> list[dict]:
    found, result = set(), []
    for row in sorted(rows, key=lambda x: (x["_when"], x["id"])):
        if row["id"] in found:
            raise ValueError("duplicate_article_identity_hold")
        result.append(row)
        found.add(row["id"])
    if len(result) > MAX_ROWS:
        raise ValueError("report_items_limit_hold")
    return result


def hourly_window(ending: datetime) -> tuple[datetime, datetime]:
    """Exact Cairo wall-clock hour; DST transitions yield UTC-safe intervals."""
    local = _clock(ending).astimezone(CAIRO)
    end = local.replace(minute=0, second=0, microsecond=0)
    return (end.astimezone(timezone.utc) - timedelta(hours=1),
            end.astimezone(timezone.utc))


def daily_window(day: date) -> tuple[datetime, datetime]:
    """Preserve current 22:00 Cairo reconciliation boundary; no cron change."""
    end = datetime.combine(day, time(22, 0), tzinfo=CAIRO)
    return ((end - timedelta(days=1)).astimezone(timezone.utc),
            end.astimezone(timezone.utc))


def choose_hourly(items: list[dict], start: datetime, end: datetime) -> list[dict]:
    return _unique([i for i in items if start <= i["_when"] < end])


def choose_daily(items: list[dict], receipts: list[dict],
                 start: datetime, end: datetime) -> list[dict]:
    """Consolidation ONLY from accepted delivery receipts, not fresh discovery.

    This is a read-only contract for a future authenticated ledger/archive
    connector. A plain JSON receipt must never be considered proof of sending.
    """
    if not isinstance(receipts, list):
        raise ValueError("delivery_receipts_required_hold")
    ids = {row["id"]: row for row in items}
    chosen, seen = [], set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("status") != "smtp_accepted":
            continue
        if (not _MAIL_ID.fullmatch(str(row.get("message_id", "")))
                or not isinstance(row.get("item_id"), str)):
            raise ValueError("delivery_receipt_identity_hold")
        when = _clock(row.get("accepted_at"))
        if not start <= when < end:
            continue
        key = row["item_id"]
        if key not in ids:
            # Accepted receipts from the other report channel are unrelated.
            continue
        if key in seen:
            raise ValueError("delivery_archive_missing_or_duplicate_hold")
        if row.get("image_sha256") != ids[key]["image_sha256"]:
            raise ValueError("daily_original_image_mismatch_hold")
        chosen.append(ids[key])
        seen.add(key)
    return _unique(chosen)



def _shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:fill"), fill)
    tc_pr.append(sh)


def _run(paragraph, content: str, *, bold: bool = False,
         color: tuple[int, int, int] | None = None, size: float | None = None):
    run = paragraph.add_run(content)
    run.bold = bold
    run.font.name = "DejaVu Sans"
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    return run


def _paragraph(doc, text: str, *, bold: bool = False, size: float = 10,
               color: tuple[int, int, int] | None = None):
    p = doc.add_paragraph()
    _rtl(p)
    _run(p, text, bold=bold, color=color, size=size)
    p.paragraph_format.space_after = Pt(6)
    return p


def _report_title(channel: str, period: str) -> str:
    category = CHANNELS[channel]
    return ("رصد | تقرير " + category + " " +
            ("الساعي" if period == "hourly" else "اليومي النهائي المجمع"))


def _verify_word_images(docx: Path, rows: list[dict]) -> None:
    doc = Document(docx)
    observed = []
    embedded = set()
    for paragraph in doc.paragraphs:
        for node in paragraph._p.xpath(".//a:blip"):
            key = node.get(qn("r:embed"))
            if key is None or key not in doc.part.related_parts:
                raise RuntimeError("word_image_relationship_hold")
            part = doc.part.related_parts[key]
            observed.append(hashlib.sha256(part.blob).hexdigest())
            embedded.add(part.partname)
    from zipfile import ZipFile
    with ZipFile(docx) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or archive.testzip() is not None:
            raise RuntimeError("word_zip_integrity_hold")
        media = [x for x in names if x.startswith("word/media/")]
    if (observed != [row["image_sha256"] for row in rows]
            or len(media) != len(rows) or len(embedded) != len(rows)):
        raise RuntimeError("word_evidence_order_or_digest_hold")
    links = {rel.target_ref for rel in doc.part.rels.values()
             if rel.reltype.endswith("/hyperlink")}
    if not {row["url"] for row in rows}.issubset(links):
        raise RuntimeError("word_original_url_missing_hold")


def render_word(channel: str, period: str, rows: list[dict],
                states: list[dict], start: datetime, end: datetime,
                destination: Path) -> dict:
    """Produce visibly watermarked NO-SEND review Word with exact proof bytes."""
    if channel not in CHANNELS or period not in {"hourly", "daily"}:
        raise ValueError("report_channel_or_period_hold")
    if not start < end:
        raise ValueError("invalid_report_window_hold")
    if len(rows) > MAX_ROWS:
        raise ValueError("report_size_hold")
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    sec.top_margin = Inches(.55)
    sec.bottom_margin = Inches(.58)
    sec.left_margin = Inches(.72)
    sec.right_margin = Inches(.72)

    normal = doc.styles["Normal"]
    normal.font.name = "DejaVu Sans"
    normal.font.size = Pt(9)
    normal.paragraph_format.space_after = Pt(3)

    heading = doc.add_paragraph()
    _rtl(heading)
    _run(heading, "وزارة التخطيط والتنمية الاقتصادية",
         bold=True, color=(14, 34, 75), size=13)
    _paragraph(doc, "رصد | نسخة مراجعة تجريبية — لم تُرسل ولا تثبت اكتمال التغطية",
               bold=True, size=9, color=(166, 120, 35))
    p = doc.add_paragraph()
    _rtl(p)
    _run(p, _report_title(channel, period),
         bold=True, color=(14, 34, 75), size=19)
    p.paragraph_format.space_after = Pt(12)

    start_c = start.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M")
    end_c = end.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M")
    _paragraph(doc, "الفترة: " + start_c + " إلى " + end_c
               + " بتوقيت القاهرة", size=10)

    total = len(rows)
    source_count = len({x["source"] for x in rows})
    available = sum(s["status"] == "ok" for s in states)
    failed = len(states) - available
    incomplete = bool(failed)
    status = ("تغطية جزئية / مصادر غير مستوفية" if incomplete else
              "تغطية المصادر المحددة فقط، وليست شاملة")
    summary = doc.add_table(rows=1, cols=2)
    summary.alignment = WD_TABLE_ALIGNMENT.CENTER
    summary.autofit = False
    for k, v in ((0, "الملخص"), (1, f"عدد المواد الموثقة في هذه المعاينة: {total}")):
        cell = summary.cell(0, k)
        _shade(cell, "0E224B" if k == 0 else "FAF1DD")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        q = cell.paragraphs[0]
        _rtl(q)
        _run(q, v, bold=True,
             color=(211, 165, 80) if k == 0 else (17, 35, 75), size=10)

    _paragraph(doc, "حالة التغطية: " + status, size=10)
    metrics = doc.add_table(rows=0, cols=2)
    metrics.style = "Table Grid"
    for label, value in [
        ("حجم الرصد المستوفي", f"{total} مادة / رابطًا أصليًا"),
        ("الناشرون ضمن المواد المقبولة", str(source_count)),
        ("المصادر المحددة التي أمكن الوصول إليها", f"{available} من {len(states)}"),
        ("المصادر المعلّقة أو غير المتاحة", str(failed)),
    ]:
        cells = metrics.add_row().cells
        cells[0].text, cells[1].text = label, value
        _shade(cells[0], "0E224B")
        _shade(cells[1], "F9F3E6")
        for idx, cell in enumerate(cells):
            for paragraph in cell.paragraphs:
                _rtl(paragraph)
                for run in paragraph.runs:
                    run.font.name = "DejaVu Sans"
                    run.font.size = Pt(9)
                    run.bold = idx == 0
                    run.font.color.rgb = RGBColor(
                        *((211, 165, 80) if idx == 0 else (15, 30, 63)))
    _paragraph(doc, "توزيع المواد حسب " +
               ("المنصة" if channel == "social" else "الموقع"), bold=True,
               size=11, color=(14, 34, 75))
    if rows:
        counter = Counter((r.get("platform") or r["source"])
                          for r in rows)
        platform_ar = {"facebook": "فيسبوك", "x": "إكس",
                       "instagram": "إنستجرام", "linkedin": "لينكدإن"}
        distribution = doc.add_table(rows=1, cols=3)
        distribution.style = "Table Grid"
        for cell, title in zip(distribution.rows[0].cells,
                               ("الموقع / المنصة", "العدد", "النسبة")):
            _shade(cell, "0E224B")
            cell.text = title
            for paragraph in cell.paragraphs:
                _rtl(paragraph)
                for run in paragraph.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(211, 165, 80)
                    run.font.name = "DejaVu Sans"
                    run.font.size = Pt(9)
        for index, (name, amount) in enumerate(counter.most_common(), 1):
            label = platform_ar.get(name, name)
            cells = distribution.add_row().cells
            for cell, value in zip(cells, (label, str(amount),
                                          f"{amount / total * 100:.1f}٪")):
                _shade(cell, "F9F3E6" if index % 2 else "FFFFFF")
                cell.text = value
                for paragraph in cell.paragraphs:
                    _rtl(paragraph)
                    for run in paragraph.runs:
                        run.font.name = "DejaVu Sans"
                        run.font.size = Pt(9)
    else:
        _paragraph(doc, "لا توجد مواد موثقة متاحة في بيانات المراجعة.", size=9)

    _paragraph(doc, "حالة المصادر — لا تُفسّر حالات عدم الوصول باعتبارها عدم وجود مواد:",
               bold=True, size=9)
    for item in states:
        _paragraph(doc, item["name"] + ": " + STATE_LABELS[item["status"]],
                   size=8)
    _paragraph(doc, (
        "تنبيه منهجي: " +
        ("لا تُدرج في التقرير اليومي سوى المواد التي ثبت قبول تسليمها "
         "في سجل موثوق مع إثبات المرفق، ولا تُعاد قراءة المنصات لصناعة المجمع."
         if period == "daily" else
         "تظهر المواد الجديدة المستوفية فقط داخل نافذة الساعة؛ "
         "المواد المتعذرة أو غير المتحققة تبقى HOLD.")
        + " هذه نسخة معاينة بلا إرسال أو اعتماد إنتاجي."
    ), size=8, color=(120, 72, 18))

    if rows:
        doc.add_page_break()
        _paragraph(doc, "المواد الموثقة — الصور والروابط الأصلية",
                   bold=True, size=13, color=(14, 34, 75))
    for i, item in enumerate(rows, 1):
        article = doc.add_paragraph()
        _rtl(article)
        article.paragraph_format.keep_with_next = True
        _run(article, f"{i}. {item['title']}",
             bold=True, color=(14, 34, 75), size=11)
        date_cairo = item["_when"].astimezone(CAIRO).strftime("%Y-%m-%d %H:%M")
        _paragraph(doc, "المصدر: " + item["source"] +
                   (" | المنصة: " + item["platform"] if channel == "social" else "")
                   + " | النشر: " + date_cairo + " القاهرة", size=8)
        link_p = doc.add_paragraph()
        _rtl(link_p)
        _word_hyperlink(link_p, item["url"], "فتح المادة الأصلية")
        link_p.paragraph_format.keep_with_next = True
        if item.get("event_label"):
            _paragraph(doc, "الموضوع: " + item["event_label"], size=8)
        caption = _paragraph(doc, "لقطة المصدر المرتبطة بهذا الرابط — "
                             "مطابقة لبصمة الصورة", size=8)
        caption.paragraph_format.keep_with_next = True
        with Image.open(item["image_path"]) as img:
            aspect = img.height / img.width
        width = min(5.8, 4.8 / aspect)
        picture = doc.add_paragraph()
        picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
        picture.add_run().add_picture(item["image_path"], width=Inches(width))
        picture.paragraph_format.keep_together = True
        if i != len(rows):
            _paragraph(doc, "ــــــــــــــــــــــــــــــــــــــــــــــــــــــــ",
                       color=(185, 142, 60), size=7)
    footer = sec.footer.paragraphs[0]
    _rtl(footer)
    _run(footer, "رصد | معاينة محلية غير مرسلة | "
         + ("ويب" if channel == "web" else "سوشيال")
         + " | " + ("ساعي" if period == "hourly" else "مجمع"),
         size=8, color=(126, 99, 55))

    doc.core_properties.title = _report_title(channel, period)
    doc.core_properties.author = "RASD REVIEW - NO SEND"
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destination)
    _verify_word_images(destination, rows)
    if not 3000 <= destination.stat().st_size <= MAX_WORD_BYTES:
        destination.unlink(missing_ok=True)
        raise RuntimeError("word_attachment_size_hold")
    return {"path": str(destination), "items": total,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "sources_available": available, "sources_limited": failed}


def build_four_reports(items: list[dict], statuses: list[dict],
                       receipts: list[dict], *, cutoff: datetime,
                       date_cairo: date, evidence_root: Path,
                       output: Path, allowed_web_hosts: set[str]) -> dict:
    """Four separate Word REVIEW artifacts; deliberately no sender/scheduler."""
    now = _clock(cutoff)
    hour_start, hour_end = hourly_window(now)
    day_start, day_end = daily_window(date_cairo)
    if not (now >= hour_end and now >= day_end):
        raise ValueError("future_daily_window_hold")
    validated, groups = [], {}
    for channel in CHANNELS:
        channel_items = [x for x in items
                         if isinstance(x, dict) and x.get("channel") == channel]
        rows = [validate_item(
            item, channel, evidence_root, allowed_web_hosts,
            cutoff=now) for item in channel_items]
        groups[channel] = _unique(rows)
    all_ids = {row["id"] for records in groups.values() for row in records}
    if any(row.get("status") == "smtp_accepted" and
           row.get("item_id") not in all_ids for row in receipts):
        raise ValueError("daily_accepted_story_missing_original_hold")
    reports = {}
    for channel in CHANNELS:
        health = _states([x for x in statuses
                          if x.get("channel") == channel], channel)
        for period in ("hourly", "daily"):
            if period == "hourly":
                selected = choose_hourly(groups[channel], hour_start, hour_end)
                start, end = hour_start, hour_end
            else:
                selected = choose_daily(groups[channel], receipts,
                                        day_start, day_end)
                start, end = day_start, day_end
            tag = f"{channel}-{period}"
            name = ("RASD-" + channel.capitalize() + "-"
                    + ("Hourly" if period == "hourly" else "Daily")
                    + "-REVIEW-NOT-SENT.docx")
            reports[tag] = render_word(
                channel, period, selected, health, start, end, output / name)
    summary = {
        "status": "REVIEW_ONLY_NO_SEND",
        "smtp_sent": False, "scheduler_changed": False,
        "live_sources_verified_by_this_builder": False,
        "daily_receipts_proven_by_this_builder": False,
        "note": ("Trusted capture and accepted-mail archive adapters still required; "
                 "receipt dictionaries alone cannot prove real source or delivery."),
        "hourly_window_utc": [hour_start.isoformat(), hour_end.isoformat()],
        "daily_window_utc": [day_start.isoformat(), day_end.isoformat()],
        "reports": reports,
    }
    (output / "RASD-Four-Reports-REVIEW-MANIFEST.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
