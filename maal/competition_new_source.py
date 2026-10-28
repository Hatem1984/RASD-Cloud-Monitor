"""Capture official publisher evidence from a REAL browser, never manually forge a case.

Owner-private local receipts; one original-page screenshot and DOM snapshot
per source. Reuses existing MA'AL Evidence validation and isolated E: storage.
No SMTP, customer credentials, production CAS, or external actions.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, date, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from html import unescape

from maal.decision_contracts import Evidence

ROOT=Path("E:/MAAL/04_HISTORICAL_QA/MAAL_COMPETITION_MVP_20261028/new_sources")
SOURCES={
 "fpt": {
   "url":"https://itida.gov.eg/English/PressReleases/Pages/fpt-opens-first-africa-office-cairo-itida-partnership.aspx",
   "publisher":"ITIDA (Egypt)",
   "title_needle":"FPT Opens Office in Cairo",
   "date":"2026-10-14",
   "date_needle":"14 October 2026",
   "angle":"market_competition",
 },
 "skills": {
   "url":"https://www.itida.gov.eg/English/PressReleases/Pages/summer-training-2026-graduates-honored.aspx",
   "publisher":"ITIDA (Egypt)",
   "title_needle":"Egypt Steps Up Investment in Technology Talent",
   "date":"2026-10-17",
   "date_needle":"17 October 2026",
   "angle":"economic_opportunity",
 },
 "eu-ai": {
   "url":"https://digital-strategy.ec.europa.eu/en/policies/enforcement-ai-act",
   "publisher":"European Commission",
   "title_needle":"enforcement framework of the AI Act",
   "date":None,
   "date_needle":"2 August 2026",
   "angle":"regulatory_change",
 },
}

def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def get_case_from_capture(folder:Path)->dict:
    """Verify screenshot bytes, HTML and page's original textual claims."""
    folder=Path(folder)
    m=json.loads((folder/"manifest.json").read_text("utf8"))
    cfg=SOURCES.get(m.get("source_key"))
    if not cfg or m.get("original_url")!=cfg["url"]:
        raise ValueError("source_url_allowlist_hold")
    html=(folder/"publisher-dom.html").read_bytes()
    img=(folder/"publisher-page.jpeg").read_bytes()
    if digest(html)!=m.get("dom_sha256") or digest(img)!=m.get("image_sha256"):
        raise ValueError("publisher_capture_sha256_hold")
    from PIL import Image
    im=Image.open(BytesIO(img))
    im.verify()
    if im.format!="JPEG":raise ValueError("publisher_original_not_jpeg")
    visible=(folder/"publisher-visible-text.txt").read_bytes()
    if digest(visible)!=m.get("visible_text_sha256"):
        raise ValueError("publisher_visible_text_digest_hold")
    text=visible.decode("utf8")
    if cfg["title_needle"].casefold() not in text.casefold():
        raise ValueError("original_headline_not_visible")
    if cfg["date_needle"].casefold() not in text.casefold():
        raise ValueError("original_publication_reference_not_visible")
    if (cfg["title_needle"].casefold() not in m.get("headline","").casefold() or
        m.get("verification_status")!="VERIFIED_ORIGINAL_PAGE" or
        m.get("capture_method")!="BROWSER_ORIGINAL_PUBLISHER_PAGE"):
        raise ValueError("publisher_capture_provenance_hold")
    published=(date.fromisoformat(cfg["date"]) if cfg["date"] else
               date(2026,8,2))
    # EU source date is the *reference obligation date*, not the publication date.
    # Do not claim that the EU page itself was published on 2 August.
    if not cfg["date"]:
        published=date.fromisoformat(m["retrieval_day"])
    ev=Evidence(m["evidence_id"],cfg["publisher"],cfg["url"],
                m["headline"],published,datetime.fromisoformat(m["observed_at"]),
                m["image_sha256"],"VERIFIED_ORIGINAL_PAGE")
    ev.validate()
    return {
        "evidence_id":ev.evidence_id,"publisher":ev.publisher,
        "original_url":ev.original_url,"headline":ev.claim,
        "published_day":cfg["date"],"date_precision":"date" if cfg["date"] else "NOT_STATED",
        "observed_at":ev.observed_at.isoformat(),"verification_status":ev.status,
        "verified_receipt":True,"timeliness":"RECENT_PUBLISHED" if cfg["date"] else "REFERENCE_ONLY",
        "evidence_digest":ev.original_page_sha256,
        "evidence_image_url":"/api/new-signal/image/"+ev.evidence_id,
        "sector_angle":cfg["angle"],"synthetic_company":True,
        "source_excerpt":text[:3200],
        "proof_method":"ORIGINAL_PUBLISHER_PAGE_SCREENSHOT",
        "source_key":m["source_key"],
    }

def capture_source(key:str)->dict:
    """Capture real HTTPS publisher webpage via Playwright, no synthetic contents."""
    cfg=SOURCES[key]
    uri=urlsplit(cfg["url"])
    if uri.scheme!="https" or uri.hostname not in (
        "itida.gov.eg","www.itida.gov.eg","digital-strategy.ec.europa.eu"):
        raise ValueError("source_host_untrusted")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":1440,"height":1000},
                                  device_scale_factor=1,locale="en-US")
            response=page.goto(cfg["url"],wait_until="domcontentloaded",timeout=30000)
            if not response or response.status!=200:
                raise ValueError("publisher_not_direct_200")
            page.wait_for_timeout(950)
            if urlsplit(page.url).hostname not in (
                "itida.gov.eg","www.itida.gov.eg","digital-strategy.ec.europa.eu"):
                raise ValueError("publisher_redirect_unapproved")
            body=page.locator("body").inner_text(timeout=8000)
            if (len(body)<900 or cfg["title_needle"].casefold() not in body.casefold()
                    or cfg["date_needle"].casefold() not in body.casefold()):
                raise ValueError("publisher_headline_or_date_unverified")
            # Headline selected from publisher rendered DOM rather than authored JSON.
            headings=[h.inner_text(timeout=2000).strip()
                      for h in page.locator("h1,h2,h3,h4").all()[:100]]
            headline=next((h for h in headings if cfg["title_needle"].casefold()
                           in h.casefold()),None)
            if not headline:raise ValueError("publisher_heading_missing")
            target=page.get_by_text(headline,exact=True).first
            target.scroll_into_view_if_needed(timeout=6000)
            page.wait_for_timeout(250)
            jpeg=page.screenshot(type="jpeg",quality=84,full_page=False)
            html=page.content().encode("utf8")
            visible=body.encode("utf8")
            observed=datetime.now(timezone.utc).isoformat()
            evidence_id=digest((cfg["url"]+"|"+digest(jpeg)).encode("utf8"))[:24]
            dest=ROOT/evidence_id
            if dest.exists():
                return get_case_from_capture(dest)
            dest.mkdir(parents=True,exist_ok=False)
            for name,blob in (("publisher-page.jpeg",jpeg),
                              ("publisher-dom.html",html),
                              ("publisher-visible-text.txt",visible)):
                with (dest/name).open("xb") as file:
                    file.write(blob);file.flush()
                    import os;os.fsync(file.fileno())
            m={
                "schema":"MAAL_REAL_PUBLISHER_CAPTURE_V1",
                "source_key":key,"original_url":cfg["url"],
                "publisher":cfg["publisher"],"headline":headline,
                "evidence_id":evidence_id,"observed_at":observed,
                "retrieval_day":observed[:10],
                "publication_date_from_page":cfg["date"],
                "capture_method":"BROWSER_ORIGINAL_PUBLISHER_PAGE",
                "verification_status":"VERIFIED_ORIGINAL_PAGE",
                "dom_sha256":digest(html),"image_sha256":digest(jpeg),
                "visible_text_sha256":digest(visible),
                "http_status":response.status,
                "redirect_checked_host":urlsplit(page.url).hostname,
                "human_editorial_approval":False,
                "smtp_sent":False,
            }
            with (dest/"manifest.json").open("x",encoding="utf8") as file:
                json.dump(m,file,ensure_ascii=False,indent=2)
                file.flush();import os;os.fsync(file.fileno())
            return get_case_from_capture(dest)
        finally:browser.close()

def verified_cases()->list[dict]:
    if not ROOT.exists():return []
    cases=[]
    for p in ROOT.iterdir():
        if p.is_dir() and (p/"manifest.json").is_file():
            try:cases.append(get_case_from_capture(p))
            except (ValueError,OSError,KeyError):continue
    return sorted(cases,key=lambda x:x["observed_at"],reverse=True)

if __name__=="__main__":
    import sys
    for name in sys.argv[1:]:
        x=capture_source(name)
        print(json.dumps({"source":name,"status":x["verification_status"],
            "evidence_id":x["evidence_id"],"original_page_image_sha256":x["evidence_digest"],
            "publication_day":x["published_day"],"headline":x["headline"],
            "observed_at":x["observed_at"]},ensure_ascii=False))
