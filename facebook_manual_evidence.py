"""Manual, local screenshot evidence intake for user-selected Facebook posts.

NOT a Facebook scraper, API or verification that the depicted post is genuine.
No network, no credentials, no email, no scheduled workflow, no private ledger.
"""
from __future__ import annotations

import hashlib
import io
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit
from zipfile import ZipFile

from docx import Document
from docx.shared import Inches, Pt
from PIL import Image, UnidentifiedImageError

from daily_report import _rtl, _word_hyperlink
from facebook_manual_validation import (
    post_identity, identity_digest, parse_operator_post_time,
    read_local_index, write_local_index,
)

MAX_ENTRIES = 20
MAX_IMAGE_BYTES = 12_000_000
MAX_SIDE = 14000
_FB_HOSTS = {"facebook.com", "www.facebook.com",
             "m.facebook.com", "web.facebook.com"}
_SENSITIVE_KEYS = {"access_token", "appsecret_proof", "token", "password",
                   "cookie", "code", "session", "auth_token"}


def is_facebook_post_url(raw: str) -> bool:
    if not isinstance(raw, str) or len(raw) > 1600:
        return False
    try:
        parsed = urlsplit(raw)
        query_keys = {key.casefold() for key, _ in
                      parse_qsl(parsed.query, keep_blank_values=True)}
        return (parsed.scheme == "https"
                and parsed.hostname in _FB_HOSTS
                and parsed.port in (None, 443)
                and parsed.username is None
                and parsed.password is None
                and bool(parsed.path.strip("/"))
                and post_identity(raw) is not None
                and not any(x in query_keys or any(x in k for k in query_keys)
                            for x in _SENSITIVE_KEYS))
    except ValueError:
        return False


def facebook_manual_search_url(keyword: str) -> str:
    """Only create a URL for the user to open manually in their browser."""
    if (not isinstance(keyword, str) or not 1 <= len(keyword.strip()) <= 120
            or any(ord(ch) < 32 for ch in keyword)):
        raise ValueError("facebook_search_keyword_hold")
    return "https://www.facebook.com/search/posts/?" + urlencode({
        "q": keyword.strip()
    })


def _read_image(path: Path) -> tuple[bytes, str]:
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("unsupported_image_format")
    if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("screenshot_missing_or_too_large")
    raw = path.read_bytes()
    if len(raw) > MAX_IMAGE_BYTES or len(raw) < 100:
        raise ValueError("screenshot_bytes_hold")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if (image.format not in {"PNG", "JPEG"}
                    or image.width > MAX_SIDE or image.height > MAX_SIDE
                    or min(image.width, image.height) < 10):
                raise ValueError("screenshot_image_hold")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("screenshot_image_hold") from None
    return raw, hashlib.sha256(raw).hexdigest()


def _validated_entries(entries: list[dict], *, now: datetime | None = None) -> list[dict]:
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError("facebook_evidence_count_hold")
    verified, seen = [], set()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("report_clock_hold")
    for entry in entries:
        if not isinstance(entry, dict) or not is_facebook_post_url(entry.get("url")):
            raise ValueError("facebook_permalink_hold")
        post_key = identity_digest(entry["url"])
        if post_key in seen:
            raise ValueError("facebook_duplicate_link_hold")
        seen.add(post_key)
        source = str(entry.get("source", "")).strip()
        note = str(entry.get("note", "")).strip()
        if not source or len(source) > 150 or len(note) > 1000:
            raise ValueError("facebook_metadata_hold")
        published = parse_operator_post_time(entry.get("published_at"), now=current)
        if entry.get("privacy_checked") is not True:
            raise ValueError("facebook_privacy_review_hold")
        path = entry.get("screenshot")
        if not isinstance(path, (str, Path)):
            raise ValueError("screenshot_path_hold")
        raw, digest = _read_image(Path(path))
        verified.append({
            "url": entry["url"], "source": source,
            "note": note, "image": raw, "sha256": digest,
            "published_at": published.isoformat(), "identity": post_key,
        })
    return verified


def build_manual_facebook_report(entries: list[dict], output_dir: Path,
                                 *, now: datetime | None = None) -> dict:
    """Evidence of *operator-provided screenshots*, NOT original-page proof."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("report_clock_hold")
    validated = _validated_entries(entries, now=current)
    # Local-only, best-effort cross-report de-duplication. No private CAS.
    seen_in_previous_reports = read_local_index(output_dir)
    current_ids = {item["identity"] for item in validated}
    if current_ids & seen_in_previous_reports:
        raise ValueError("facebook_duplicate_prior_report_hold")
    doc = Document()
    doc.styles["Normal"].font.name = "DejaVu Sans"
    doc.styles["Normal"].font.size = Pt(10)
    section = doc.sections[0]
    section.top_margin = Inches(.65)
    section.bottom_margin = Inches(.6)
    title = doc.add_paragraph(style="Title")
    _rtl(title)
    title.add_run("رصد | تقرير لقطات منشورات فيسبوك — مراجعة يدوية")
    for value in (
        "التصنيف: أدلة قدمها المشغل يدويًا — غير متحقق منها آليًا.",
        "عدد المنشورات: " + str(len(validated))
        + " | تاريخ إعداد التقرير: " + current.strftime("%Y-%m-%d %H:%M UTC"),
        "تواريخ النشر وأسماء الصفحات أدخلها المشغّل؛ لم يتم التحقق منها عبر Meta.",
        "تنبيه: الصورة من اختيار المشغل؛ لم تُلتقط آليًا من فيسبوك. "
        "يجب مقارنة الصورة بالمنشور الأصلي والتحقق من تاريخ النشر وهوية الصفحة "
        "وإزالة أي بيانات شخصية غير لازمة قبل مشاركة التقرير.",
        "وجود منشور عن الوزارة لا يثبت صحة مضمونه. "
        "لم تُستخدم صلاحيات حساب فيسبوك أو API أو أي محرك بحث آلي.",
    ):
        p = doc.add_paragraph()
        _rtl(p)
        p.add_run(value)
    for index, item in enumerate(validated, 1):
        p = doc.add_paragraph()
        _rtl(p)
        p.add_run(f"{index}. " + item["source"]).bold = True
        p = doc.add_paragraph()
        _rtl(p)
        p.add_run("تاريخ النشر حسب إدخال المشغّل (غير متحقق آليًا): "
                  + item["published_at"])
        p = doc.add_paragraph()
        _rtl(p)
        _word_hyperlink(p, item["url"], "رابط منشور فيسبوك الذي أدخله المشغل")
        if item["note"]:
            p = doc.add_paragraph()
            _rtl(p)
            p.add_run("ملاحظات المشغل (غير متحققة): " + item["note"])
        p = doc.add_paragraph()
        _rtl(p)
        p.add_run("بصمة SHA-256 للصورة التي قدمها المشغل: " + item["sha256"])
        picture = doc.add_paragraph()
        _rtl(picture)
        picture.add_run().add_picture(io.BytesIO(item["image"]), width=Inches(5.8))
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / (
        "RASD-Facebook-Manual-Screenshots-"
        + current.strftime("%Y%m%d-%H%M%S-%f") + ".docx"
    )
    doc.save(dest)
    # Verify exact pixels/source image bytes embedded in DOCX (no invisible swap).
    with ZipFile(dest) as output:
        embedded_digests = {
            hashlib.sha256(output.read(name)).hexdigest()
            for name in output.namelist() if name.startswith("word/media/")
        }
    if any(item["sha256"] not in embedded_digests for item in validated):
        dest.unlink(missing_ok=True)
        raise ValueError("screenshot_embedded_digest_mismatch")
    try:
        write_local_index(output_dir, seen_in_previous_reports | current_ids)
    except (OSError, ValueError):
        dest.unlink(missing_ok=True)
        raise ValueError("facebook_index_update_hold") from None
    return {"status": "MANUAL_FACEBOOK_EVIDENCE_UNVERIFIED",
            "word": str(dest), "items": len(validated),
            "email_sent": False, "network_requests": False}


def main() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    root = tk.Tk()
    root.title("رصد — توثيق منشورات فيسبوك يدويًا")
    root.geometry("800x330")
    items: list[dict] = []
    status = tk.StringVar(value="اختر صورة شاشة التقطتها بنفسك، وأدخل رابط المنشور.")

    ttk.Label(root, text="رصد | توثيق لقطات فيسبوك",
              font=("Tahoma", 15, "bold")).pack(pady=15)
    ttk.Label(root, text="لا يتم البحث الآلي أو الدخول إلى حسابك. "
              "مطلوب رابط منشور أصلي وتاريخ نشر واضح ومراجعة خصوصية. "
              "المنشورات تحتاج مراجعة قبل اعتمادها.",
              wraplength=640).pack(pady=4)

    def open_manual_search() -> None:
        # This opens the user's own browser; it does NOT automate collection.
        terms_file = Path(__file__).with_name("sources_newsroom_active.json")
        try:
            terms = json.loads(terms_file.read_text(encoding="utf-8"))["keywords"]
            default = terms[0] if terms else "وزارة التخطيط"
        except (ValueError, OSError, KeyError, TypeError):
            default = "وزارة التخطيط"
        keyword = simpledialog.askstring(
            "بحث فيسبوك يدوي", "الكلمة المفتاحية التي تريد البحث عنها:",
            initialvalue=default)
        if keyword is None:
            return
        try:
            url = facebook_manual_search_url(keyword)
        except ValueError:
            messagebox.showerror("رصد", "الكلمة المفتاحية غير صالحة.")
            return
        webbrowser.open(url)
        status.set("فتحنا صفحة بحث فيسبوك في متصفحك. "
                   "اختار المنشورات والتقط الصور بنفسك لإضافتها للتقرير.")

    def add() -> None:
        if len(items) >= MAX_ENTRIES:
            messagebox.showwarning("رصد", "الحد الأقصى 20 لقطة لكل تقرير.")
            return
        filename = filedialog.askopenfilename(
            title="اختر لقطة شاشة التقطتها", filetypes=[
                ("صور الشاشة", "*.png *.jpg *.jpeg")])
        if not filename:
            return
        link = simpledialog.askstring("المنشور الأصلي", "رابط المنشور (https):")
        if not link:
            return
        name = simpledialog.askstring(
            "المصدر", "اسم الصفحة الأصلية كما يظهر على المنشور (إجباري):")
        if not name:
            return
        published_at = simpledialog.askstring(
            "تاريخ النشر",
            "أدخل تاريخ النشر الظاهر على المنشور مع المنطقة الزمنية:\n"
            "مثال: 2026-11-08T11:30:00+02:00\n"
            "الوقت المُدخل سيُصنّف غير متحقق منه آليًا.")
        if not published_at:
            return
        note = simpledialog.askstring(
            "ملاحظة", "مقتطف أو ملاحظة المشغّل (غير متحققة، اختيارية):") or ""
        privacy_checked = messagebox.askyesno(
            "مراجعة الخصوصية",
            "هل راجعت الصورة يدويًا وتأكدت من عدم وجود بيانات شخصية "
            "غير ضرورية قبل إضافتها للتقرير؟\n"
            "التأكيد لا يعني إثبات أصالة المنشور.")
        if not privacy_checked:
            return
        candidate = {"url": link.strip(), "source": name,
                     "published_at": published_at.strip(),
                     "privacy_checked": True,
                     "note": note, "screenshot": filename}
        try:
            _validated_entries([candidate])
        except (ValueError, OSError):
            messagebox.showerror("رصد", "الرابط أو الصورة غير صالحين للتقرير.")
            return
        if any(identity_digest(previous["url"]) ==
               identity_digest(candidate["url"]) for previous in items):
            messagebox.showwarning("رصد", "هذا المنشور أُضيف بالفعل.")
            return
        items.append(candidate)
        status.set(f"الصور المسجلة: {len(items)}. تقدر تضيف منشورات أخرى أو تنشئ التقرير.")

    def save() -> None:
        if not items:
            messagebox.showwarning("رصد", "لا توجد لقطات مسجلة.")
            return
        try:
            report = build_manual_facebook_report(
                items, Path(__file__).resolve().parent / "report-output" / "facebook")
        except (ValueError, OSError) as exc:
            if "duplicate_prior_report" in str(exc):
                messagebox.showerror(
                    "رصد", "المنشور أُدرج من قبل في تقرير محلي سابق؛ "
                    "لم يتم إنشاء تقرير مكرر.")
            else:
                messagebox.showerror(
                    "رصد", "التواريخ أو الصور أو سجل التكرار غير صالح؛ "
                    "لم يتم إنشاء تقرير.")
            return
        status.set("تم إنشاء تقرير محلي للمراجعة: " + report["word"])
        messagebox.showinfo("تم", "تم إنشاء Word محلي للمراجعة فقط.\n" + report["word"])

    buttons = ttk.Frame(root)
    buttons.pack(pady=20)
    ttk.Button(buttons, text="فتح بحث فيسبوك", command=open_manual_search).pack(side="left", padx=8)
    ttk.Button(buttons, text="إضافة لقطة منشور", command=add).pack(side="left", padx=8)
    ttk.Button(buttons, text="إنشاء تقرير فيسبوك Word", command=save).pack(side="left", padx=8)
    ttk.Label(root, textvariable=status, wraplength=620,
              justify="center").pack(padx=16, pady=10)
    root.mainloop()


if __name__ == "__main__":
    main()
