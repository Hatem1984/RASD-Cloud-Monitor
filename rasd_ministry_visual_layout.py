"""Arabic RASD media-clipping layout matching the approved visual reference.

Used for original screenshot-verified hourly bulletins AND accepted daily archives.
No discovery, network, private ledger, email or PDF conversion happens here.
All JPEG bytes are embedded unchanged and independently checked by the caller.
"""
from __future__ import annotations

from collections import Counter
from math import ceil
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

NAVY = "0C2047"
GOLD = "C7A252"
CREAM = "FAF6E8"
WHITE = "FFFFFF"
SOURCE_NAMES = {
    "Hapi native news RSS": "حابي", "Al Masry Al Youm native news RSS": "المصري اليوم",
    "Al Shorouk native Economy RSS": "الشروق", "Alborsa native Egyptian Economy RSS": "البورصة",
    "Masrawy native Egypt news RSS": "مصراوي", "Al Massa native news RSS": "المساء",
    "Al Nahar Egypt native news RSS": "النهار",
    "Al Mal native publisher HTML": "المال",
    "Sada El Balad native news RSS": "صدى البلد", "Veto native news RSS": "فيتو",
    "Daily News Egypt native RSS": "ديلي نيوز إيجيبت", "Egypt Independent native RSS": "إيجيبت إندبندنت",
    "Egyptian Streets native RSS": "إيجيبشن ستريتس", "Sky News Arabia native RSS": "سكاي نيوز عربية",
    "National Planning Institute native RSS": "المعهد القومي للتخطيط",
}


def _shade(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), color)


def _rtl(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    ppr = paragraph._p.get_or_add_pPr()
    bidi = ppr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
        ppr.append(bidi)
    bidi.set(qn("w:val"), "1")


def _run(paragraph, label: str, *, size=10, bold=False, color=NAVY):
    run = paragraph.add_run(label)
    run.bold = bold
    run.font.name = "DejaVu Sans"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    # Word/LibreOffice treat Arabic as a complex script. Without w:szCs
    # headings declared as 26pt can render at the default ~11pt size.
    properties = run._r.get_or_add_rPr()
    cs_size = properties.find(qn("w:szCs"))
    if cs_size is None:
        cs_size = OxmlElement("w:szCs")
        properties.append(cs_size)
    cs_size.set(qn("w:val"), str(int(round(size * 2))))
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.insert(0, fonts)
    fonts.set(qn("w:cs"), "DejaVu Sans")
    return run


def _link(paragraph, url: str, text="رابط الخبر الأصلي") -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    relationship = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "165C91")
    properties.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    run.append(properties)
    node = OxmlElement("w:t")
    node.text = text
    run.append(node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _border(cell, color=GOLD) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    borders = tcpr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcpr.append(borders)
    for edge in ("top", "bottom", "left", "right"):
        element = OxmlElement("w:" + edge)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "9")
        element.set(qn("w:color"), color)
        borders.append(element)


def _section_header(section) -> None:
    header = section.header.paragraphs[0]
    _rtl(header)
    _run(header, "وزارة التخطيط والتنمية الاقتصادية", size=8.5, bold=True)
    footer = section.footer.paragraphs[0]
    _rtl(footer)
    _run(footer, "رصد المواقع الإلكترونية  |  نسخة إلكترونية  |  ", size=8, color="666666")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)


def _cover(doc, *, date_label: str, period_label: str, stories: int, sites: int,
           report_period: str = "daily", report_kind: str = "") -> None:
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    table.columns[0].width = Cm(18)
    row = table.rows[0]
    row.height = Cm(25.2)
    row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    cell = row.cells[0]
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _shade(cell, NAVY)
    _border(cell, GOLD)
    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "وزارة التخطيط والتنمية الاقتصادية", size=16, bold=True, color=GOLD)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    _run(p, "تقرير رصد", size=26, bold=True, color=WHITE)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "المواقع الإلكترونية", size=25, bold=True, color=WHITE)
    if report_period == "interval":
        p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        period_label_ar = ("تقرير المتابعة النصف ساعية" if report_kind == "half_hourly"
                           else "تقرير المتابعة الساعية")
        _run(p, period_label_ar, size=17, bold=True, color=GOLD)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(16)
    _run(p, "بتاريخ " + date_label, size=11, color=GOLD)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "فترة الرصد:", size=11, bold=True, color=GOLD)
    # Split the 22:00 Cairo window into two short, readable lines rather
    # than one line of long mixed Arabic/Latin digits crossing cell edges.
    for endpoint in period_label.split(" إلى ", 1):
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, endpoint.strip(), size=10, color=GOLD)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(30)
    _run(p, f"التغطيات المصوّرة: {stories}    |    المواقع الممثلة: {sites}",
         size=14, bold=True, color=GOLD)
    doc.add_page_break()



def descriptive_topic_counts(articles: list[dict]) -> Counter:
    """Count headline/excerpt topics only; no AI, inference or sentiment scores.

    One publisher coverage may match several topics. Totals are deliberately
    NOT presented as an exhaustive partition of distinct news events.
    """
    import re

    topics = (
        ("ريادة الأعمال والشركات الناشئة",
         ("الشركات الناشئة", "شركات ناشئة", "ريادة الاعمال",
          "رواد الاعمال", "مسرعات الاعمال")),
        ("الاستثمار والقطاع الخاص",
         ("الاستثمار", "استثمارات", "القطاع الخاص",
          "الصندوق السيادي", "الطروحات الحكومية")),
        ("خطط التنمية والمؤشرات",
         ("خطة التنمية", "النمو الاقتصادي", "مؤشرات النمو",
          "التحول الاقتصادي", "السردية الوطنية", "الاصلاحات الهيكلية")),
        ("الشراكات والتمويل",
         ("تمويل", "شراكة", "شراكات", "البنك الدولي",
          "البنك الاسيوي", "المؤسسات الدولية")),
        ("التحول الرقمي والمعرفة",
         ("الذكاء الاصطناعي", "التحول الرقمي", "الرقمنة",
          "تكنولوجيا المعلومات", "الابتكار الرقمي")),
        ("التنمية البشرية والاجتماعية",
         ("التنمية البشرية", "حياة كريمة", "الفقر",
          "الحماية الاجتماعية", "الصحة", "التعليم")),
    )
    def norm(value):
        if not isinstance(value, str):
            return ""
        return re.sub(
            r"[\u0610-\u061a\u064b-\u065f\u0670\u0640]",
            "", value).translate(str.maketrans(
                {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}
            )).casefold()

    counts = Counter()
    for article in articles:
        text = norm(article.get("headline")) + " " + norm(
            article.get("publisher_excerpt"))
        matched = False
        for label, terms in topics:
            if any(norm(term) in text for term in terms):
                counts[label] += 1
                matched = True
        if not matched:
            counts["متابعات أخرى غير مصنفة"] += 1
    return counts


def _summary(doc, report: dict, distribution: Counter) -> None:
    # The legacy SMTP subject is a transport label, NOT the Ministry Word
    # identity. Display the independent RASD brand within this report only;
    # never change the SMTP subject or recipient mailbox rules here.
    period = report.get("report_period", "daily")
    title = report["title"]
    display_title = ("رصد | " + title[len("مآل | "):]
                     if title.startswith("مآل | ") else title)
    p=doc.add_paragraph(); _rtl(p); _run(p, display_title, size=10, color="777777")
    p=doc.add_paragraph(); _rtl(p); _run(p, "تحليل الرصد", size=20, bold=True)
    p=doc.add_paragraph(); _rtl(p)
    basis = ("أخبار الساعة السابقة واستدراكات من ساعات أقدم، مع تاريخ النشر الحقيقي لكل مادة."
             if period == "interval" and report.get("report_kind") == "hourly"
             else "من روابط الناشرين الأصلية المستوفية خلال فترة المتابعة."
             if period == "interval" else "وفق سجل التسليم فقط.")
    _run(p, f"الملخص: إجمالي التغطيات الموثقة {len(report['articles'])}؛ "
          f"عدد المواقع الممثلة {len(distribution)}، {basis}",
          size=11, bold=True)
    if period == "interval" and report.get("report_kind") == "hourly":
        fresh, older = report.get("hourly_in_period"), report.get("hourly_recovered")
        if (type(fresh) is not int or type(older) is not int or
                fresh < 0 or older < 0 or fresh + older != len(report["articles"]) or
                any(item.get("hourly_publication_bucket") not in
                    {"within_previous_hour", "recovered_older"}
                    for item in report["articles"]) or
                sum(item["hourly_publication_bucket"] == "within_previous_hour"
                    for item in report["articles"]) != fresh):
            raise ValueError("rasd_visual_hourly_publication_classification_hold")
        p=doc.add_paragraph(); _rtl(p)
        _run(p,f"نُشر خلال الساعة المكتملة السابقة: {fresh} تغطية؛ "
              f"استدراك أخبار منشورة قبلها: {older}. "
              "لا تُحسب الاستدراكات ضمن مستهدف الأخبار الجديدة للساعة.",
              size=10.5,bold=True)
    p=doc.add_paragraph(); _rtl(p)
    _run(p, "توزيع التغطيات على المواقع", size=14, bold=True)
    summary=doc.add_table(rows=1, cols=3)
    summary.autofit=False
    summary.columns[0].width=Cm(9)
    summary.columns[1].width=Cm(3)
    summary.columns[2].width=Cm(5)
    for idx,label in enumerate(("الموقع", "الأخبار", "النسبة")):
        c=summary.rows[0].cells[idx];_shade(c,NAVY)
        p=c.paragraphs[0];_rtl(p);_run(p,label,size=10,bold=True,color=GOLD)
    total=len(report['articles'])
    for label,count in sorted(distribution.items(),key=lambda kv:(-kv[1],kv[0])):
        cells=summary.add_row().cells
        vals=(label,str(count),f"{(count/total)*100:.1f}%")
        for i,v in enumerate(vals):
            if i==0:_shade(cells[i],CREAM)
            p=cells[i].paragraphs[0];_rtl(p);_run(p,v,size=9.5,bold=i==0)
    topic_counts=descriptive_topic_counts(report["articles"])
    if topic_counts:
        p=doc.add_paragraph();_rtl(p)
        _run(p,"المحاور الموضوعية — تحليل وصفي",size=13,bold=True)
        for topic,count in sorted(topic_counts.items(),
                                  key=lambda row:(-row[1],row[0])):
            p=doc.add_paragraph();_rtl(p)
            _run(p,f"{topic}: {count} تغطية",size=9.5)
        p=doc.add_paragraph();_rtl(p)
        _run(p,"تصنيف بالكلمات الواردة في عناوين الناشرين وموجزاتهم. "
              "قد تنتمي التغطية لأكثر من محور؛ لا يُعد هذا "
              "تحليلًا للمشاعر أو قياسًا للأثر أو حصرًا للأحداث المستقلة.",
              size=8.5,color="666666")
    p=doc.add_paragraph();_rtl(p)
    _run(p,"حالة التغطية: ",size=11,bold=True)
    _run(p, ("هذه حصيلة الأخبار التي ثبتت صور صفحاتها الأصلية خلال فترة المتابعة؛ لا تثبت شمول كل ما نُشر أو سلامة المصادر المتعذرة."
             if period == "interval" else
             "هذه حصيلة الأخبار التي سبق تسليمها بصورها والتحقق من ملفاتها؛ لا تثبت شمول كل ما نُشر خلال اليوم."),size=10)
    p=doc.add_paragraph();_rtl(p)
    _run(p,"بيان الوزارة: ",size=11,bold=True)
    _run(p,"غير محسوم من سجل البريد؛ يتطلب مطابقة المصدر الرسمي مباشرة.",size=10)
    p=doc.add_paragraph();_rtl(p)
    if distribution:
        site,count=max(distribution.items(),key=lambda x:x[1])
        _run(p,f"أكثر المواقع حضورًا في النشرة: {site} ({count} تغطية).",size=11,bold=True)
    p=doc.add_paragraph();_rtl(p)
    _run(p, ("تنبيه توثيق: صور هذه المتابعة ملتقطة من صفحات الناشرين الأصلية، "
             "ويُتحقق من بصمات JPEG داخل ملف Word قبل إرسال التقرير."
             if period == "interval" else
             "تنبيه توثيق: جميع الصور المعروضة محفوظة من ملفات أصلية سبق إرسالها، "
             "ويجري فحص تطابق بصمات JPEG مع كل خبر قبل تسليم هذا المستند."),size=9)
    if period == "interval":
        sources = report.get("sources")
        if (not isinstance(sources, list) or not sources or
                any(row.get("status") not in {"ok", "failed"} for row in sources)):
            raise ValueError("rasd_visual_interval_health_missing_hold")
        healthy = sum(row["status"] == "ok" for row in sources)
        p=doc.add_paragraph();_rtl(p)
        _run(p,f"حالة مصادر الرصد: {healthy} متاح من {len(sources)}؛ "
              f"{len(sources)-healthy} متعذر. المصدر المتعذر لا يعني عدم وجود أخبار.",size=9,bold=True)
        held = report.get("held_candidates", [])
        if not isinstance(held, list):
            raise ValueError("rasd_visual_interval_held_untrusted")
        if held:
            p=doc.add_paragraph();_rtl(p)
            _run(p,f"مواد مطابقة معلّقة ولم تُسلّم: {len(held)}؛ "
                  "لم تُحسب ضمن التغطيات الموثقة.",size=9,bold=True)
    scope = report.get("scope_note")
    if scope is not None:
        if not isinstance(scope, str) or len(scope) > 1200:
            raise ValueError("rasd_visual_source_scope_untrusted")
        if scope.strip():
            p=doc.add_paragraph();_rtl(p)
            _run(p,"نطاق المصادر الفعلي: "+scope,size=9,bold=True)
    if report.get("limitations"):
        p=doc.add_paragraph();_rtl(p);_run(p,"حدود التقرير: "+report["limitations"],size=8.5)
    # Editorial index also makes the original publisher titles selectable and
    # searchable in Word; the picture pages remain the primary visual record.
    p=doc.add_paragraph();_rtl(p);_run(p,"عناوين التغطيات الموثقة",size=12,bold=True)
    for index,item in enumerate(report["articles"][:12],1):
        p=doc.add_paragraph();_rtl(p)
        _run(p,f"{index:02d} — {item['headline']}",size=8)
    if len(report["articles"])>12:
        p=doc.add_paragraph();_rtl(p)
        _run(p,f"باقي العناوين ({len(report['articles'])-12}) موضحة داخل البطاقات المصوّرة.",size=8)
    doc.add_page_break()


def _card(cell, item: dict, index: int, *, wide: bool = False) -> None:
    source=SOURCE_NAMES.get(item["source"],item["source"])
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.TOP
    _border(cell,"DFD0A9")
    p=cell.paragraphs[0];_rtl(p);_shade(cell,CREAM)
    _run(p,f"{index:02d}  |  {source}",size=11,bold=True)
    p=cell.add_paragraph();_rtl(p)
    _run(p,item["headline"],size=8.5,bold=True)
    if item.get("hourly_publication_bucket") == "recovered_older":
        p=cell.add_paragraph();_rtl(p)
        _run(p,"استدراك: نُشر قبل الساعة الحالية للرصد، ويُعرض بتاريخ نشره الأصلي.",
             size=8,bold=True)
    image_path=Path(item["evidence_image_path"])
    with Image.open(image_path) as pic:
        width,height=pic.size
        if width<100 or height<100:
            raise ValueError("rasd_visual_original_image_invalid")
    # A single original clipping should be readable, not half-width
    # beside a blank second column. Multi-clipping spreads stay 2-column.
    max_w,max_h=(16.0,14.2) if wide else (7.65,7.2)
    fitted_w=min(max_w,max_h*width/height)
    fitted_h=fitted_w*height/width
    p=cell.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(image_path),width=Cm(fitted_w),height=Cm(fitted_h))
    p=cell.add_paragraph();_rtl(p)
    _run(p,"النشر: "+(item.get("published_display_cairo") or item.get("published_at_cairo", "غير محدد")),size=8)
    p=cell.add_paragraph();_rtl(p);_link(p,item["url"])



def render_ministry_no_accepted_word(report: dict, destination: Path) -> None:
    """Use the ministry-style cover for a daily operational ZERO-delivery notice.

    Never confuse zero previously delivered original screenshots with no
    publisher news. This path inserts neither fabricated articles nor images.
    """
    if (report.get("coverage") != "NO_ACCEPTED_VERIFIED_NEWS" or
            report.get("articles") != [] or
            report.get("verified_links") != 0):
        raise ValueError("rasd_visual_zero_status_untrusted")

    doc = Document()
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21)
    section.top_margin = Cm(1.35)
    section.bottom_margin = Cm(1.35)
    section.left_margin = Cm(1.4)
    section.right_margin = Cm(1.4)
    section.header_distance = Cm(0.65)
    section.footer_distance = Cm(0.7)
    section.different_first_page_header_footer = True
    _section_header(section)
    doc.styles["Normal"].font.name = "DejaVu Sans"
    doc.styles["Normal"].font.size = Pt(10)

    end = report.get("display_window_end", "فترة غير محددة")
    start = report.get("display_window_start", "فترة غير محددة")
    _cover(doc, date_label=end, period_label=start + " إلى " + end,
           stories=0, sites=0)

    p = doc.add_paragraph()
    _rtl(p)
    _run(p, "تقرير حالة الرصد — لا أخبار مصوّرة مُسلّمة", size=18, bold=True)
    p = doc.add_paragraph()
    _rtl(p)
    _run(p, "هذه نتيجة مراجعة سجل التسليم خلال الفترة، وليست شهادة بعدم نشر أخبار.",
         size=12, bold=True)
    p = doc.add_paragraph()
    _rtl(p)
    _run(p, "الأخبار المصوّرة التي اجتازت التحقق وأُرسلت خلال الفترة: 0.",
         size=12)
    p = doc.add_paragraph()
    _rtl(p)
    _run(p, "قد تكون هناك أخبار منشورة لم تُسلّم بسبب تعذر وصول المصدر "
         "أو رفض التقاط صورة الصفحة الأصلية أو انتظار المراجعة.", size=11)
    limitations = report.get("limitations", "")
    if limitations:
        p = doc.add_paragraph()
        _rtl(p)
        _run(p, "حدود التغطية: " + limitations, size=10)
    doc.core_properties.title = "رصد | تقرير حالة رصد المواقع الإلكترونية"
    doc.core_properties.author = "RASD"
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destination)


def render_ministry_visual_word(report: dict, destination: Path) -> None:
    """Share ONE layout; keep interval captures separate from accepted daily archive."""
    period = report.get("report_period", "daily")
    if period == "daily":
        if report.get("coverage") != "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS":
            raise ValueError("rasd_visual_layout_requires_accepted_sent_originals")
    elif period == "interval":
        if (report.get("ministry_media_grid") is not True or
                report.get("report_kind") not in {"half_hourly", "hourly"} or
                report.get("coverage") not in {"HEALTHY", "SOURCE_LIMITED"}):
            raise ValueError("rasd_visual_interval_status_untrusted")
    else:
        raise ValueError("rasd_visual_period_untrusted")
    articles=report.get("articles",[])
    # 7 publisher coverages/hour * 24h = 168. Bounded at 180.
    if not articles or len(articles)>180:
        raise ValueError("rasd_visual_invalid_article_count")
    if any(not isinstance(row.get("evidence_image_path"),str) or
           not Path(row["evidence_image_path"]).is_file() or
           not row.get("url","").startswith("https://") or
           not row.get("headline") or not row.get("source")
           for row in articles):
        raise ValueError("rasd_visual_missing_original_evidence")

    doc=Document()
    section=doc.sections[0]
    section.page_height=Cm(29.7);section.page_width=Cm(21)
    section.top_margin=Cm(1.35);section.bottom_margin=Cm(1.35)
    section.left_margin=Cm(1.4);section.right_margin=Cm(1.4)
    section.header_distance=Cm(0.65);section.footer_distance=Cm(0.7)
    section.different_first_page_header_footer=True
    _section_header(section)
    doc.styles["Normal"].font.name="DejaVu Sans"
    doc.styles["Normal"].font.size=Pt(9)
    doc.styles["Normal"].paragraph_format.space_after=Pt(4)

    distribution=Counter(SOURCE_NAMES.get(row["source"],row["source"]) for row in articles)
    end=report.get("display_window_end", "فترة غير محددة")
    period=report.get("display_window_start", "غير محدد")+" إلى "+end
    _cover(doc,date_label=end,period_label=period,
           stories=len(articles),sites=len(distribution),
           report_period=report.get("report_period", "daily"),
           report_kind=report.get("report_kind", ""))
    _summary(doc,report,distribution)
    for start in range(0,len(articles),4):
        p=doc.add_paragraph();_rtl(p)
        _run(p,"المواقع الإلكترونية — صور صفحات الأخبار الأصلية",size=15,bold=True)
        p.paragraph_format.space_after=Pt(8)
        segment=articles[start:start+4]
        if len(segment) == 1:
            table = doc.add_table(rows=1, cols=1)
            table.autofit = False
            table.columns[0].width = Cm(18)
            _card(table.rows[0].cells[0], segment[0], start + 1,
                  wide=True)
        else:
            table=doc.add_table(rows=ceil(len(segment)/2),cols=2)
            table.autofit=False
            table.columns[0].width=Cm(9)
            table.columns[1].width=Cm(9)
            for offset,item in enumerate(segment):
                cell=table.rows[offset//2].cells[offset%2]
                _card(cell,item,start+offset+1)
        if start+4<len(articles):
            doc.add_page_break()
    doc.core_properties.title=(report["title"] if report.get("report_period") == "interval"
                               else "رصد | تقرير رصد المواقع الإلكترونية")
    doc.core_properties.author="RASD"
    destination.parent.mkdir(parents=True,exist_ok=True)
    doc.save(destination)