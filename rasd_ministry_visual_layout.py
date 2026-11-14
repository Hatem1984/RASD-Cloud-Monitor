"""Arabic RASD media-clipping layout matching the approved visual reference.

Used ONLY for a validated archive of delivered original publisher screenshots.
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


def _cover(doc, *, date_label: str, period_label: str, stories: int, sites: int) -> None:
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
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(16)
    _run(p, "بتاريخ " + date_label, size=11, color=GOLD)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "الفترة: " + period_label, size=10, color=GOLD)
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(45)
    _run(p, f"{stories}  تغطية مصوّرة     |     {sites}  مواقع", size=15, bold=True, color=GOLD)
    doc.add_page_break()


def _summary(doc, report: dict, distribution: Counter) -> None:
    p=doc.add_paragraph(); _rtl(p); _run(p, report["title"], size=10, color="777777")
    p=doc.add_paragraph(); _rtl(p); _run(p, "تحليل الرصد", size=20, bold=True)
    p=doc.add_paragraph(); _rtl(p)
    _run(p, f"الملخص: {len(report['articles'])} تغطية موثقة من {len(distribution)} موقعًا داخل سجل التسليم.", size=11, bold=True)
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
    p=doc.add_paragraph();_rtl(p)
    _run(p,"حالة التغطية: ",size=11,bold=True)
    _run(p,"هذه حصيلة الأخبار التي سبق تسليمها بصورها والتحقق من ملفاتها؛ لا تثبت شمول كل ما نُشر خلال اليوم.",size=10)
    p=doc.add_paragraph();_rtl(p)
    _run(p,"بيان الوزارة: ",size=11,bold=True)
    _run(p,"غير محسوم من سجل البريد؛ يتطلب مطابقة المصدر الرسمي مباشرة.",size=10)
    p=doc.add_paragraph();_rtl(p)
    if distribution:
        site,count=max(distribution.items(),key=lambda x:x[1])
        _run(p,f"أكثر المواقع حضورًا في النشرة: {site} ({count} تغطية).",size=11,bold=True)
    p=doc.add_paragraph();_rtl(p)
    _run(p,"تنبيه توثيق: جميع الصور المعروضة محفوظة من ملفات أصلية سبق إرسالها، "
          "ويجري فحص تطابق بصمات JPEG مع كل خبر قبل تسليم هذا المستند.",size=9)
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


def _card(cell, item: dict, index: int) -> None:
    source=SOURCE_NAMES.get(item["source"],item["source"])
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.TOP
    _border(cell,"DFD0A9")
    p=cell.paragraphs[0];_rtl(p);_shade(cell,CREAM)
    _run(p,f"{index:02d}  |  {source}",size=11,bold=True)
    p=cell.add_paragraph();_rtl(p)
    _run(p,item["headline"],size=8.5,bold=True)
    image_path=Path(item["evidence_image_path"])
    with Image.open(image_path) as pic:
        width,height=pic.size
        if width<100 or height<100:
            raise ValueError("rasd_visual_original_image_invalid")
    max_w,max_h=7.65,7.2
    fitted_w=min(max_w,max_h*width/height)
    fitted_h=fitted_w*height/width
    p=cell.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(image_path),width=Cm(fitted_w),height=Cm(fitted_h))
    p=cell.add_paragraph();_rtl(p)
    _run(p,"النشر: "+(item.get("published_display_cairo") or item.get("published_at_cairo", "غير محدد")),size=8)
    p=cell.add_paragraph();_rtl(p);_link(p,item["url"])


def render_ministry_visual_word(report: dict, destination: Path) -> None:
    """Format previously SENT verified screenshots; never infer missing news."""
    if report.get("coverage")!="CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS":
        raise ValueError("rasd_visual_layout_requires_accepted_sent_originals")
    articles=report.get("articles",[])
    if not articles or len(articles)>60:
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
           stories=len(articles),sites=len(distribution))
    _summary(doc,report,distribution)
    for start in range(0,len(articles),4):
        p=doc.add_paragraph();_rtl(p)
        _run(p,"المواقع الإلكترونية — صور صفحات الأخبار الأصلية",size=15,bold=True)
        p.paragraph_format.space_after=Pt(8)
        segment=articles[start:start+4]
        table=doc.add_table(rows=ceil(len(segment)/2),cols=2)
        table.autofit=False
        table.columns[0].width=Cm(9)
        table.columns[1].width=Cm(9)
        for offset,item in enumerate(segment):
            cell=table.rows[offset//2].cells[offset%2]
            _card(cell,item,start+offset+1)
        if start+4<len(articles):
            doc.add_page_break()
    doc.core_properties.title="رصد | تقرير رصد المواقع الإلكترونية"
    doc.core_properties.author="RASD"
    destination.parent.mkdir(parents=True,exist_ok=True)
    doc.save(destination)