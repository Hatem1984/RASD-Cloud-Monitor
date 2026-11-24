"""Add verified date-only Ministry originals to the existing daily Word, never send."""
from __future__ import annotations
import hashlib
import tempfile
from datetime import date
from pathlib import Path
from zipfile import ZipFile
from docx import Document
from docx.shared import Cm
from PIL import Image
from cloud_proof_report import word_images_match_capture_digests
from daily_report import _word_hyperlink
from official_ministry_source import canonical_official_article
from rasd_ministry_visual_layout import _rtl, _run

MAX_WORD_BYTES = 8_000_000
MAX_OFFICIAL = 15

def _proofs(word):
    doc = Document(word)
    result = []
    for shape in doc.inline_shapes:
        ref = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
        part = doc.part.related_parts[ref]
        result.append({"status":"verified","sha256":hashlib.sha256(part.blob).hexdigest()})
    if result:
        if not word_images_match_capture_digests(word, result):
            raise RuntimeError("daily_official_base_media_hold")
    else:
        with ZipFile(word) as z:
            if z.testzip() is not None or any(x.startswith("word/media/") for x in z.namelist()):
                raise RuntimeError("daily_official_base_media_hold")
    return result

def append_official_daily(base: Path, output: Path, *, target_day: date, builder=None):
    """Keep base report intact; append verified official originals or explicit HOLD.

    Date-only publisher evidence is a distinct section, not part of the
    22:00-to-22:00 accepted-news counts. No new message or private state.
    """
    if type(target_day) is not date or not base.is_file():
        raise ValueError("daily_official_invalid_input")
    base_proof = _proofs(base)
    def links(word):
        return {r.target_ref for r in Document(word).part.rels.values()
                if r.reltype.endswith("/hyperlink") and r.is_external}
    base_links = links(base)
    if builder is None:
        from rasd_official_daily import build_official_daily
        builder = lambda path, *, target_date: build_official_daily(
            path, target_date=target_date, time_budget_seconds=120)
    with tempfile.TemporaryDirectory(prefix="rasd-official-section-", dir=output) as tmp:
        work = Path(tmp)
        rows = []
        status = "HOLD"
        try:
            original, records = builder(work, target_date=target_day)
            if not 1 <= len(records) <= MAX_OFFICIAL:
                raise ValueError("official_count_invalid")
            seen = set()
            for row in records:
                url = row["url"]
                image = Path(row["image_path"])
                sha = row["sha256"]
                if (row.get("status") != "verified" or canonical_official_article(url) != url
                        or url in seen or row["published_date_cairo"] != target_day.isoformat()
                        or not isinstance(row["headline"], str) or not 16 <= len(row["headline"]) <= 350
                        or not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != sha):
                    raise ValueError("official_receipt_invalid")
                seen.add(url)
                rows.append(row)
            if not word_images_match_capture_digests(original, [
                    {"status":"verified","sha256":r["sha256"]} for r in rows]):
                raise ValueError("official_word_digest_invalid")
            status = "VERIFIED_FIRST_PAGE"
        except RuntimeError as exc:
            rows = []
            if str(exc) == "official_no_verified_new_original_today":
                status = "NO_VERIFIED_DATE_MATCH_FIRST_PAGE"
        except Exception:
            rows = []
        def render(selected, section_status):
            doc = Document(base)
            doc.add_page_break()
            p=doc.add_paragraph(); _rtl(p); _run(p,"البيانات والأخبار الرسمية للوزارة",size=18,bold=True)
            p=doc.add_paragraph(); _rtl(p)
            _run(p,"قسم مستقل عن حصيلة الرسائل الصحفية السابقة. نطاقه الصفحة الأولى من قائمة أخبار الوزارة؛ التاريخ المنشور: "+target_day.isoformat()+"، دون إسناد ساعة نشر غير موثقة. لا يثبت حصر جميع البيانات أو مطابقة نافذة 22:00 إلى 22:00.",size=10)
            p=doc.add_paragraph(); _rtl(p)
            if section_status=="VERIFIED_FIRST_PAGE":
                _run(p,"عدد البيانات الرسمية الموثقة في هذا القسم: "+str(len(selected)),bold=True)
            elif section_status=="NO_VERIFIED_DATE_MATCH_FIRST_PAGE":
                _run(p,"لم يثبت وجود بيانات بتاريخ اليوم ضمن الصفحة الأولى المفحوصة؛ لا يعني عدم نشر بيانات أخرى.",bold=True)
            else:
                _run(p,"حالة التغطية الرسمية: معلقة (HOLD) — تعذر إكمال التحقق من المصدر أو الصور أو التاريخ أو حجم المرفق؛ لا تُحتسب بيانات غير موثقة.",bold=True)
            section=doc.sections[-1]
            available=(section.page_width-section.left_margin-section.right_margin)/360000
            for row in selected:
                doc.add_page_break()
                p=doc.add_paragraph(); _rtl(p); _run(p,row["headline"],size=13,bold=True)
                p=doc.add_paragraph(); _rtl(p); _run(p,"تاريخ النشر الرسمي: "+row["published_date_cairo"]+" (دون ساعة موثقة)")
                p=doc.add_paragraph(); _rtl(p); _word_hyperlink(p,row["url"],"رابط البيان الأصلي")
                image=Path(row["image_path"])
                with Image.open(image) as pic:
                    w,h=pic.size
                width=min(available-0.4,16,19*w/h)
                doc.add_paragraph().add_run().add_picture(str(image),width=Cm(width))
            dest=work/"combined.docx"
            doc.save(dest)
            expected=base_proof+[{"status":"verified","sha256":r["sha256"]} for r in selected]
            expected_links = base_links | {r["url"] for r in selected}
            if (links(dest) != expected_links or _proofs(dest) != expected
                    or not 3000 <= dest.stat().st_size <= MAX_WORD_BYTES):
                raise RuntimeError("daily_official_combined_integrity_or_size_hold")
            return dest
        try:
            combined=render(rows,status)
        except Exception:
            rows=[];status="HOLD"
            try:
                combined=render(rows,status)
            except Exception:
                # Do not lose the existing accepted-news report on optional
                # section failure; public run status explicitly records HOLD.
                return base,"HOLD_BASE_REPORT_PRESERVED",0
        dest=output/"RASD-Daily-With-Official-Section.docx"
        combined.replace(dest)
        return dest,status,len(rows)
