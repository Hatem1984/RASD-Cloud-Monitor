"""RASD daily read-only Arabic Word/PDF digest of validated original RSS headlines.

Manual cloud report only. Never sends Gmail, reads private credentials or
mutates persistent state. RSS headline coverage is not comprehensive news coverage.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gate11_runner import candidate_from_feed
from monitor import inspect, read_feed

CAIRO = ZoneInfo("Africa/Cairo")
WINDOW_HOURS = 24
MAX_ARTICLES = 15


def gather(config: dict, *, fetch=read_feed, now: datetime | None = None) -> dict:
    checked = datetime.now(timezone.utc) if now is None else now
    if checked.tzinfo is None:
        raise ValueError("naive_report_clock_forbidden")
    checked = checked.astimezone(timezone.utc)
    observed = inspect(config, fetch=fetch, now=checked)
    since = checked - timedelta(hours=WINDOW_HOURS)
    articles = []
    for original in observed["matched_public_articles"]:
        article = candidate_from_feed(original, config, checked)
        if article is None:
            continue
        stamp = parsedate_to_datetime(article["published"]).astimezone(timezone.utc)
        # Reports never represent future-dated RSS items as recent published news.
        if not since <= stamp <= checked:
            continue
        articles.append({
            "id": article["id"],
            "headline": article["headline"],
            "source": article["source"],
            "url": article["url"],
            "published_at_cairo": stamp.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M %Z"),
            "_published_utc": stamp,
        })
    articles.sort(key=lambda x: x["_published_utc"], reverse=True)
    for article in articles:
        del article["_published_utc"]
    sources = [{
        "feed_id": item["feed_id"],
        "status": item["status"],
        "verified_links": item["verified_links"],
        "headline_matches": item["headline_matches"],
        "error_type": item.get("error") if item["status"] != "ok" else None,
    } for item in observed["sources"]]
    coverage = "DEGRADED" if any(s["status"] != "ok" for s in sources) else "HEALTHY"
    return {
        "title": "رصد | التقرير الإخباري اليومي",
        "window_start_cairo": since.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M %Z"),
        "window_end_cairo": checked.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M %Z"),
        "coverage": coverage,
        "verified_links": observed["public_verified_publisher_links"],
        "rss_matches": observed["planning_headline_matches"],
        "articles": articles[:MAX_ARTICLES],
        "sources": sources,
        "limitations": (
            "النتائج مبنية على عناوين قنوات RSS الأصلية لمصدرين معتمدين فقط. "
            "قد تتأخر القنوات أو تغفل أخباراً؛ هذه ليست تغطية إعلامية شاملة. "
            "الحد الأقصى للعرض 15 خبراً مطابقاً، ولا يتم اختلاق أخبار عند عدم وجود نتائج."
        ),
        "email_sent": False,
        "scheduler_enabled": False,
        "private_state_used": False,
    }


def _rtl(paragraph):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    p_pr.append(bidi)


def _word_hyperlink(paragraph, url):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement("w:r")
    prop = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "086A80")
    prop.append(color)
    run.append(prop)
    text = OxmlElement("w:t")
    text.text = url
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def render_docx(report: dict, destination: Path) -> None:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)
    styles = doc.styles
    styles["Normal"].font.name = "DejaVu Sans"
    styles["Normal"].font.size = Pt(10)
    styles["Normal"].font.color.rgb = RGBColor(36, 52, 69)
    styles["Title"].font.name = "DejaVu Sans"
    styles["Title"].font.size = Pt(19)
    styles["Title"].font.color.rgb = RGBColor(8, 106, 128)

    p = doc.add_paragraph(style="Title")
    _rtl(p)
    p.add_run(report["title"])
    p = doc.add_paragraph()
    _rtl(p)
    p.add_run("الفترة: " + report["window_start_cairo"] + " إلى " + report["window_end_cairo"])
    p = doc.add_paragraph()
    _rtl(p)
    p.add_run(
        "حالة المصادر: " + report["coverage"] +
        " | روابط الناشرين المفحوصة: " + str(report["verified_links"]) +
        " | أخبار مطابقة خلال 24 ساعة: " + str(len(report["articles"]))
    )

    header = doc.add_paragraph()
    _rtl(header)
    header.add_run("الأخبار المطابقة").bold = True
    if not report["articles"]:
        no_items = doc.add_paragraph()
        _rtl(no_items)
        no_items.add_run("لم يُعثر على أخبار جديدة مطابقة في المصادر المتاحة خلال الفترة المحددة.")
    else:
        for index, article in enumerate(report["articles"], 1):
            p = doc.add_paragraph()
            _rtl(p)
            run = p.add_run(str(index) + ". " + article["headline"])
            run.bold = True
            meta = doc.add_paragraph()
            _rtl(meta)
            meta.add_run("المصدر: " + article["source"] + " | النشر: " + article["published_at_cairo"])
            link_paragraph = doc.add_paragraph()
            _rtl(link_paragraph)
            _word_hyperlink(link_paragraph, article["url"])
    p = doc.add_paragraph()
    _rtl(p)
    p.add_run("حالة المصادر").bold = True
    for feed in report["sources"]:
        p = doc.add_paragraph()
        _rtl(p)
        p.add_run(
            feed["feed_id"] + ": " + feed["status"] +
            " | روابط: " + str(feed["verified_links"]) +
            (" | فشل: " + feed["error_type"] if feed["error_type"] else "")
        )
    p = doc.add_paragraph()
    _rtl(p)
    p.add_run("تنبيه منهجي: " + report["limitations"])
    doc.core_properties.title = report["title"]
    doc.core_properties.author = "RASD"
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destination)


def render_html(report: dict) -> str:
    esc = lambda val: html.escape(str(val), quote=True)
    def article_html(article, i):
        return (
            '<section class="article"><h2>' + str(i) + ". " + esc(article["headline"]) +
            '</h2><p class="meta">' + esc(article["source"]) + " | " +
            esc(article["published_at_cairo"]) + "</p><p class='url'>" +
            esc(article["url"]) + "</p></section>"
        )
    articles = "".join(article_html(article, i)
                       for i, article in enumerate(report["articles"], 1))
    if not articles:
        articles = '<p class="empty">لم يُعثر على أخبار جديدة مطابقة خلال آخر 24 ساعة.</p>'
    sources = "".join(
        "<li>" + esc(s["feed_id"]) + ": " + esc(s["status"]) +
        " (" + esc(s["verified_links"]) + " رابط)" +
        (" - " + esc(s["error_type"]) if s["error_type"] else "") + "</li>"
        for s in report["sources"]
    )
    status = "تغطية متدهورة: أحد المصادر غير متاح" if report["coverage"] == "DEGRADED" else "المصادر المتاحة سليمة"
    return (
        '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
        '<title>RASD Arabic daily report</title><style>'
        '@page{size:A4;margin:17mm 16mm;}'
        'html,body{margin:0;padding:0;background:white;color:#243445;}'
        'body{font-family:"DejaVu Sans","Noto Sans Arabic",sans-serif;font-size:12px;line-height:1.9;}'
        'header{border-bottom:3px solid #086a80;padding-bottom:12px;margin-bottom:18px;}'
        'h1{font-size:25px;color:#086a80;margin:0 0 8px;}'
        'h2{font-size:15px;color:#243445;line-height:1.6;margin:0 0 6px;}'
        '.meta{color:#536c7d;margin:0 0 4px;}'
        '.url{color:#086a80;font-size:9px;direction:ltr;text-align:left;overflow-wrap:anywhere;}'
        '.article{padding:10px 0;border-bottom:1px solid #dae7ec;break-inside:avoid;}'
        '.badge{font-size:11px;color:#495f6b;}'
        '.empty{border:1px solid #cbdde3;border-radius:6px;padding:14px;}'
        'footer{border-top:1px solid #dae7ec;margin-top:22px;font-size:10px;color:#617582;}'
        '</style></head><body><header><h1>' + esc(report["title"]) +
        '</h1><div>' + esc(report["window_start_cairo"]) + " إلى " +
        esc(report["window_end_cairo"]) + '</div><div class="badge">' + esc(status) +
        " | روابط الناشرين: " + esc(report["verified_links"]) +
        " | الأخبار المدرجة: " + esc(len(report["articles"])) +
        "</div></header><main>" + articles +
        '<h2>حالة مصادر RSS</h2><ul>' + sources +
        '</ul></main><footer>' + esc(report["limitations"]) + '</footer></body></html>'
    )


def render_pdf(report: dict, destination: Path) -> None:
    from playwright.sync_api import sync_playwright

    markup = render_html(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(accept_downloads=False, service_workers="block")
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(markup, wait_until="load")
            page.pdf(path=str(destination), format="A4", print_background=True,
                     prefer_css_page_size=True)
        finally:
            browser.close()
    if not destination.is_file() or destination.stat().st_size < 2500:
        raise RuntimeError("pdf_report_render_invalid")


def generate(config_path: Path, output_dir: Path, *, fetch=read_feed,
             now: datetime | None = None) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    report = gather(config, fetch=fetch, now=now)
    # Names include only the Cairo calendar day; no article bodies, personal
    # information or credentials are placed into artifacts.
    stamp = report["window_end_cairo"][:10]
    docx = output_dir / ("RASD-Daily-" + stamp + ".docx")
    pdf = output_dir / ("RASD-Daily-" + stamp + ".pdf")
    render_docx(report, docx)
    render_pdf(report, pdf)
    return {"mode": "manual_public_daily_report",
            "word_created": docx.is_file(),
            "pdf_created": pdf.is_file(),
            "articles": len(report["articles"]),
            "sources_healthy": sum(s["status"] == "ok" for s in report["sources"]),
            "sources_failed": sum(s["status"] != "ok" for s in report["sources"]),
            "coverage": report["coverage"],
            "email_sent": False,
            "scheduler_enabled": False,
            "private_state_used": False}


def main():
    parser = argparse.ArgumentParser(description="Generate source-backed Arabic RASD Word and PDF")
    parser.add_argument("--output-dir", type=Path, default=Path("report-output"))
    args = parser.parse_args()
    try:
        result = generate(Path("sources.json"), args.output_dir)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if result["coverage"] == "DEGRADED":
            print("::warning::RASD daily report source coverage DEGRADED", flush=True)
    except Exception:
        print("rasd_daily_report_failed_closed", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
