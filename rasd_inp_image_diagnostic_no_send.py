"""Diagnose original INP article photo under EXISTING strict first-party guard.

Read 1 qualifying original RSS article, inspect real visible article img states
after 0, 1 and 3 seconds on the same source page. Never save or publish an
image, original URL, HTML, title or private content; never bypass offsite
assets/403/rate limits; never send email.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from capture_public import allowed_url, original_headline_h1_index
from gate11_runner import candidate_from_feed
from monitor import parse_rss, read_feed

PUBLISHER = "inp.edu.eg"


def photo_classification(stages: list[list[dict]]) -> str:
    if not stages or not isinstance(stages, list):
        return "IMAGE_STATES_INVALID_HOLD"
    first = stages[0]
    last = stages[-1]
    if not isinstance(first, list) or not isinstance(last, list):
        return "IMAGE_STATES_INVALID_HOLD"
    for rows in stages:
        if (not isinstance(rows, list) or any(
            not isinstance(row, dict) or
            type(row.get("visible")) is not bool or
            type(row.get("loaded")) is not bool or
            row.get("origin") not in ("first_party", "external", "invalid")
            for row in rows
        )):
            return "IMAGE_STATES_INVALID_HOLD"
    missing = [x for x in last if x["visible"] and not x["loaded"]]
    if not missing:
        if any(x["visible"] and not x["loaded"] for x in first):
            return "ORIGINAL_IMAGE_LOADED_AFTER_BOUNDED_WAIT"
        return "ORIGINAL_VISIBLE_IMAGES_LOADED"
    if any(x["origin"] == "external" for x in missing):
        return "EXTERNAL_ARTICLE_IMAGE_BLOCKED_BY_ORIGIN_POLICY"
    if any(x["origin"] == "invalid" for x in missing):
        return "ORIGINAL_IMAGE_URL_UNTRUSTED_HOLD"
    return "FIRST_PARTY_ORIGINAL_ARTICLE_IMAGE_STILL_UNLOADED"


def observe_image_state(page) -> list[dict]:
    return page.evaluate("""(publisher) => Array.from(
      document.querySelectorAll('article img, .entry-content img, .post-content img, .article-content img')
    ).map(img => {
      const r = img.getBoundingClientRect();
      const st = getComputedStyle(img);
      const visible = r.width >= 300 && r.height >= 150 &&
        r.bottom > 0 && r.top < innerHeight && r.right > 0 &&
        r.left < innerWidth && st.visibility !== 'hidden' &&
        st.display !== 'none';
      let origin = 'invalid';
      try {
        const host = new URL(img.currentSrc || img.src, document.baseURI).hostname;
        origin = (host === publisher || host.endsWith('.' + publisher)) ?
           'first_party' : 'external';
      } catch (_) {}
      return {visible, loaded: img.complete && img.naturalWidth >= 80, origin};
    })""", PUBLISHER)


def run_qa() -> dict:
    cfg = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    feeds = [x for x in cfg["feeds"] if x["id"] == "inp_official"]
    if len(feeds) != 1:
        raise RuntimeError("inp_approved_source_not_unique")
    feed = feeds[0]
    if feed["url"] != "https://inp.edu.eg/feed/" or feed["allowed_article_hosts"] != ["inp.edu.eg"]:
        raise RuntimeError("inp_approved_origin_changed")
    now = datetime.now(timezone.utc)
    raw = read_feed(feed["url"], cfg["max_feed_bytes"])
    _, original_items = parse_rss(
        raw, feed, cfg["keywords"], now, cfg["recent_hours"],
        require_complete_items=True)
    selected = next((x for row in original_items
                     if (x := candidate_from_feed(row, cfg, now)) is not None),
                    None)
    receipt = {
        "mode": "RASD_INP_ORIGINAL_IMAGE_ROOT_CAUSE_NO_SEND",
        "source_id": "inp_official",
        "matching_original_rss_candidates": len(original_items),
        "examined_original_pages": 0,
        "photo_status": "NO_RELEVANT_ORIGINAL_ITEM",
        "stage_counts": [],
        "http_status": None, "emails_sent": 0,
        "new_assets_authorized": False,
    }
    if not selected:
        return receipt
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
            try:
                context = browser.new_context(
                    viewport={"width":1200,"height":900},
                    locale="ar-EG",service_workers="block",
                    ignore_https_errors=False)
                context.route("**/*", lambda route: (
                    route.continue_() if allowed_url(route.request.url,PUBLISHER,asset=True)
                    else route.abort()))
                page = context.new_page()
                receipt["examined_original_pages"] = 1
                response = page.goto(selected["url"], wait_until="domcontentloaded",
                                     timeout=26000)
                code = response.status if response else None
                receipt["http_status"] = code if code in (200,401,403,404,429,500,502,503,504) else None
                if not response or code != 200 or not allowed_url(page.url,PUBLISHER):
                    receipt["photo_status"] = "ORIGINAL_PAGE_HTTP_OR_REDIRECT_HOLD"
                    return receipt
                title = page.title()
                body = page.locator("body").inner_text(timeout=10000)
                h1 = page.locator("h1")
                idx = original_headline_h1_index(title,body,h1.all_inner_texts())
                if idx is None:
                    receipt["photo_status"] = "ORIGINAL_HEADING_UNVERIFIED_HOLD"
                    return receipt
                headline=h1.nth(idx)
                headline.scroll_into_view_if_needed(timeout=4000)
                headline.evaluate("""element => window.scrollTo(0,
                    Math.max(0,window.scrollY + element.getBoundingClientRect().top - 120))""")
                page.wait_for_timeout(1600)
                stages=[observe_image_state(page)]
                page.wait_for_timeout(1000)
                stages.append(observe_image_state(page))
                page.wait_for_timeout(2000)
                stages.append(observe_image_state(page))
                receipt["stage_counts"] = [{
                   "visible_original_images":sum(y["visible"] for y in rows),
                   "visible_unloaded":sum(y["visible"] and not y["loaded"] for y in rows),
                   "visible_external":sum(y["visible"] and y["origin"]=="external" for y in rows)
                } for rows in stages]
                receipt["photo_status"]=photo_classification(stages)
            finally:
                browser.close()
    except Exception as error:
        receipt["photo_status"]=(
            type(error).__name__ if type(error).__name__ in
            ("TimeoutError","Error","ValueError") else "OTHER_BROWSER_HOLD")
    return receipt


if __name__=="__main__":
    print(json.dumps(run_qa(),ensure_ascii=False,sort_keys=True))
