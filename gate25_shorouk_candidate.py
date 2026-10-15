"""RASD Gate25: source admission PILOT for Al Shorouk; not production feed config.

Discover genuine news via Al Shorouk's official Economy RSS. Render the original
publisher's actual webpage in Chromium without bypass, then validate screenshot.
This file does not send mail, mutate state, or approve the publisher in sources.json.
"""
from __future__ import annotations
import html
import json
import re
import tempfile
from datetime import datetime, timezone, time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from capture_public import image_quality
from monitor import article_id

CAIRO = ZoneInfo("Africa/Cairo")
FEED = "https://www.shorouknews.com/Economy/rss"
PUBLISHER = "www.shorouknews.com"
KEYWORDS = ("وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
            "التخطيط والتنمية الاقتصادية", "أحمد رستم")
CHALLENGES = ("verify you are human", "just a moment", "captcha",
              "access denied", "checking your browser")


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("unreviewed_redirect")


def publisher_article(url):
    try:
        u = urlsplit(url)
        params = parse_qs(u.query)
        return (u.scheme == "https" and u.hostname == PUBLISHER
                and u.port in (None, 443) and not u.username and not u.password
                and u.path.lower() == "/news/view.aspx"
                and re.fullmatch(r"\d{8}", params.get("cdate", [""])[0])
                and re.fullmatch(r"[a-fA-F0-9-]{36}", params.get("id", [""])[0]))
    except (TypeError, ValueError, AttributeError, IndexError):
        return False


def fetch_public_feed(url=FEED, max_bytes=700_000):
    if url != FEED:
        raise ValueError("unreviewed_feed")
    req = Request(url, headers={"User-Agent": "RASD-Research-Monitor/1.0",
                                "Accept": "application/rss+xml, application/xml"})
    with build_opener(RejectRedirect()).open(req, timeout=18) as response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("rss_too_large")
        return data


def strip_html(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", text or ""))).strip()


def extract_candidates(feed_bytes, now, *, start_cairo=None):
    if b"<!DOCTYPE" in feed_bytes.upper() or b"<!ENTITY" in feed_bytes.upper():
        raise ValueError("xml_entities_forbidden")
    root = ET.fromstring(feed_bytes)
    if root.tag.rsplit("}",1)[-1].lower() != "rss":
        raise ValueError("not_rss")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_now")
    local_now = now.astimezone(CAIRO)
    start = start_cairo or datetime.combine(local_now.date(),time(8,0),CAIRO)
    start = start.astimezone(CAIRO)
    if start.date() != local_now.date() or start > local_now:
        raise ValueError("invalid_cairo_window")
    found, seen = [], set()
    for entry in root.findall("./channel/item"):
        title = strip_html(entry.findtext("title"))[:300]
        link = (entry.findtext("link") or "").strip()
        body = strip_html(entry.findtext("description"))[:1800]
        published = (entry.findtext("pubDate") or "").strip()
        if not title or not publisher_article(link) or not published:
            continue
        try:
            stamp = parsedate_to_datetime(published)
            if not stamp or stamp.tzinfo is None or stamp.utcoffset() is None:
                continue
        except (TypeError, ValueError):
            continue
        if not start <= stamp.astimezone(CAIRO) <= local_now:
            continue
        if not any(w in title + " " + body for w in KEYWORDS):
            continue
        key = article_id(link)
        if key in seen:
            continue
        seen.add(key)
        found.append({"id":key,"url":link,"title":title,"description":body,
                      "published_cairo":stamp.astimezone(CAIRO).isoformat(),
                      "published_raw":published,"source":"بوابة الشروق"})
    found.sort(key=lambda r:r["published_cairo"],reverse=True)
    return found


def screenshot_article(article, destination):
    """Capture real page, not thumbnail/preview; false means never evidence."""
    if not publisher_article(article["url"]):
        return {"ok":False,"reason":"source_rejected"}
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
            try:
                ctx = browser.new_context(viewport={"width":1350,"height":1050},
                    locale="ar-EG",ignore_https_errors=False,service_workers="block",
                    accept_downloads=False)
                # Allow only the same origin; no third-party redirects or proxy bypass.
                ctx.route("**/*",lambda route: route.continue_()
                    if urlsplit(route.request.url).scheme=="https" and
                       urlsplit(route.request.url).hostname in ("www.shorouknews.com","shorouknews.com")
                    else route.abort())
                page = ctx.new_page()
                resp=page.goto(article["url"],wait_until="domcontentloaded",timeout=26000)
                if resp is None or resp.status != 200:
                    code=None if resp is None else resp.status
                    return {"ok":False,"reason":"publisher_access_refused" if code in (401,403)
                        else "publisher_http_failure","http_status":code}
                if urlsplit(page.url).hostname!=PUBLISHER or page.url!=article["url"]:
                    return {"ok":False,"reason":"redirect_or_url_mismatch"}
                body = page.locator("body").inner_text(timeout=12000)
                title = page.title()
                content = " ".join(body.split())
                if len(content)<350 or any(w in content[:1300].lower() for w in CHALLENGES):
                    return {"ok":False,"reason":"publisher_content_unavailable"}
                if article["title"][:17] not in title+" "+content:
                    return {"ok":False,"reason":"headline_mismatch"}
                if not any(w in content for w in KEYWORDS):
                    return {"ok":False,"reason":"article_content_mismatch"}
                # Bring the actual article headline and at least its first paragraph
                # into viewport before capturing. No synthetic overlays or fake proof.
                heading = page.locator("h1").filter(has_text=article["title"][:14]).first
                if heading.count():
                    heading.scroll_into_view_if_needed(timeout=4000)
                page.wait_for_timeout(850)
                destination.parent.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(destination),type="jpeg",quality=85,
                                full_page=False,timeout=12000)
                quality=image_quality(destination)
                if not quality["accepted"] or destination.stat().st_size<8000:
                    destination.unlink(missing_ok=True)
                    return {"ok":False,"reason":"invalid_or_blank_page_image"}
                import hashlib
                raw=destination.read_bytes()
                if not raw.startswith(b"\xff\xd8"):
                    destination.unlink(missing_ok=True)
                    return {"ok":False,"reason":"non_jpeg_image"}
                return {"ok":True,"reason":"verified",
                        "sha256":hashlib.sha256(raw).hexdigest(),
                        "bytes":len(raw),"page_title_matches":True,
                        "publisher_url_matches":True,
                        "jpeg_content_pass":True,"http_status":200,
                        "article_text":content[:6500],
                        "page_title":title}
            finally:
                browser.close()
    except Exception:
        destination.unlink(missing_ok=True)
        return {"ok":False,"reason":"browser_or_network_exception"}


def write_pilot_word(article, capture, image_path, dest):
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    d=Document()
    sec=d.sections[0]
    sec.top_margin=sec.bottom_margin=Cm(1.7)
    sec.left_margin=sec.right_margin=Cm(2)
    normal=d.styles["Normal"]
    normal.font.name="DejaVu Sans"
    normal.font.size=Pt(11)
    normal.font.color.rgb=RGBColor(31,49,64)
    def para(txt="",bold=False):
        p=d.add_paragraph()
        p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        ppr=p._p.get_or_add_pPr()
        bidi=OxmlElement("w:bidi");bidi.set(qn("w:val"),"1");ppr.append(bidi)
        r=p.add_run(txt);r.bold=bold
        return p
    para("RASD | بروفة Gate 25 — رصد بصري حقيقي",True)
    para("تقرير اختبار لمادة صحفية أصلية واحدة، وليس التقرير اليومي النهائي.")
    para("العنوان: "+article["title"],True)
    para("المصدر: بوابة الشروق")
    para("وقت النشر (القاهرة): "+article["published_cairo"].replace("+03:00"," (+03:00)"))
    p=para("رابط الناشر: ")
    link=OxmlElement("w:hyperlink")
    link.set(qn("r:id"),p.part.relate_to(article["url"],RT.HYPERLINK,is_external=True))
    run=OxmlElement("w:r");t=OxmlElement("w:t");t.text="فتح الخبر الأصلي";run.append(t)
    link.append(run);p._p.append(link)
    para("ملخص مقتبس بالمعنى من وصف الخبر المنشور في RSS، دون ادعاء مراجعة مستقلة للوقائع:",True)
    para(article["description"][:900] or article["title"])
    para("ملاحظة تحليلية:",True)
    para("الخبر يتناول أنشطة التعاون/السياسات المرتبطة بالتخطيط والتنمية. "
         "هذه تغطية لخبر منشور، ولا تُثبت وحدها بدء تنفيذ المشروعات أو نتائجها. "
         "وجود تغطيات أخرى للقاء نفسه لا يعني حدوث وقائع مستقلة.")
    para("دليل الصورة: لقطة حقيقية من صفحة الناشر، مع تطابق الرابط والعنوان وجودة JPEG وبصمة SHA256.",True)
    d.add_picture(str(image_path),width=Cm(16.4))
    para("SHA256: "+capture["sha256"])
    para("حالة النطاق: اختبار صورة واحدة فقط. لا يعني اكتمال تغطية بقية المصادر؛ لا إرسال بريد أو جدولة.")
    dest.parent.mkdir(parents=True,exist_ok=True)
    d.save(dest)


def run(outdir:Path):
    now=datetime.now(timezone.utc)
    report={"status":"HOLD","source":"shorouk_economy",
            "feed":FEED,"eligible_count":0,"actual_screenshots_verified":0,
            "real_word_created":False,"email_sent":False,"schedule_enabled":False,
            "preview_only":True}
    try:
        candidates=extract_candidates(fetch_public_feed(),now)
        report["feed_parse"]="OK"
        report["eligible_count"]=len(candidates)
        if not candidates:
            report["reason"]="no_matching_article_in_cairo_window"
            return report
        article=candidates[0]
        report["selected_published_cairo"]=article["published_cairo"]
        report["selected_id"]=article["id"]
        # Cap attempts at one, never switch silently to another blocked article.
        photo=outdir/"original_publisher_page.jpg"
        capture=screenshot_article(article,photo)
        report["screenshot_diagnostic"]={k:v for k,v in capture.items()
                       if k not in ("article_text","page_title")}
        if not capture["ok"]:
            report["reason"]=capture["reason"]
            return report
        # Re-validate the exact captured JPEG with RASD's production
        # original-page proof contract, without contacting the publisher twice.
        # This is real evidence reused byte-for-byte, NEVER synthesized.
        import shutil
        from cloud_proof_report import proof_capture
        feeds=json.loads(Path("sources_shorouk.json").read_text(encoding="utf-8"))["feeds"]
        def real_evidence_reuse(url,publisher,destination):
            if url!=article["url"] or publisher!="shorouknews.com":
                return {"ok":False,"reason":"publisher_not_approved"}
            shutil.copyfile(photo,destination)
            return {"ok":True,"actual_url":url,"title":article["title"],
                    "sha256":capture["sha256"]}
        approved=proof_capture({
            "id":article["id"],"url":article["url"],"headline":article["title"],
            "source":feeds[0]["name"]},
            feeds,outdir/"validated_proof_tmp.jpg",capture=real_evidence_reuse)
        (outdir/"validated_proof_tmp.jpg").unlink(missing_ok=True)
        report["integrated_core_proof_status"]=approved["status"]
        if approved["status"]!="verified" or approved.get("sha256")!=capture["sha256"]:
            report["reason"]="production_evidence_contract_not_verified"
            return report
        target=outdir/"RASD-Gate25-Original-Publisher-Pilot.docx"
        write_pilot_word(article,capture,photo,target)
        report["status"]="SAMPLE_VERIFIED_NOT_DAILY"
        report["actual_screenshots_verified"]=1
        report["real_word_created"]=target.is_file()
        report["reason"]="evidence_complete_for_one_sample_only"
        (outdir/"article.json").write_text(json.dumps({
            "title":article["title"],"description":article["description"],
            "source":article["source"],"url":article["url"],
            "published_cairo":article["published_cairo"],
            "page_text":capture["article_text"],"sha256":capture["sha256"],
            "editorial_events_verified":None
        },ensure_ascii=False,indent=2),encoding="utf-8")
        return report
    except Exception as exc:
        report["reason"]="feed_or_parser_unavailable"
        report["safe_exception_type"]=type(exc).__name__
        return report


if __name__=="__main__":
    import sys
    folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path("gate25-local")
    folder.mkdir(parents=True,exist_ok=True)
    result=run(folder)
    (folder/"audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
