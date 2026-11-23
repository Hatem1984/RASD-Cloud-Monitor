"""Optional strict on-demand screenshot of a reviewed original publisher.

No planning-specific keyword check; article H1 must independently agree with
the tenant-matched RSS headline. No source bypass, image substitution, or SMTP.
Requires opt-in Playwright Chromium on the local demo host.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from capture_public import (
    APPROVED_PUBLISHERS, allowed_url, original_article_images_loaded,
    original_headline_h1_index, headline_visible_in_viewport,
    capture_verified_original_frame,
)
from monitor import _matchable_arabic


def capture_manual_article(article: dict, dest: Path) -> dict:
    if article["demo"]:
        return {"ok":False,"reason":"demo_image_is_not_original"}
    original=article["url"]
    publisher=next((p for p in APPROVED_PUBLISHERS if allowed_url(original,p)),None)
    if not publisher:
        return {"ok":False,"reason":"publisher_not_reviewed_for_screenshot"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok":False,"reason":"playwright_not_installed_on_local_demo"}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        try:
            context=browser.new_context(viewport={"width":1200,"height":900},
                locale="ar-EG",device_scale_factor=1,service_workers="block",
                accept_downloads=False,ignore_https_errors=False)
            context.route("**/*",lambda route: (
                route.continue_() if allowed_url(route.request.url,publisher,asset=True)
                else route.abort()))
            page=context.new_page()
            response=page.goto(original,wait_until="domcontentloaded",timeout=26000)
            if response is None or response.status!=200 or page.url!=original:
                return {"ok":False,"reason":"publisher_http_or_redirect_hold"}
            body=page.locator("body").inner_text(timeout=10000)
            if len(body)<180:
                return {"ok":False,"reason":"original_page_body_unavailable"}
            headings=page.locator("h1")
            if not headings.count():
                return {"ok":False,"reason":"publisher_h1_missing"}
            index=original_headline_h1_index(page.title(),body,headings.all_inner_texts())
            if index is None:
                return {"ok":False,"reason":"publisher_h1_ambiguous"}
            h=headings.nth(index)
            expected=set(_matchable_arabic(article["title"]).split()[:8])
            actual=set(_matchable_arabic(h.inner_text()).split()[:12])
            if len(expected&actual)<min(3,len(expected)):
                return {"ok":False,"reason":"publisher_h1_rss_title_mismatch"}
            h.scroll_into_view_if_needed(timeout=4000)
            h.evaluate("""element => window.scrollTo(
                0,Math.max(0,window.scrollY+element.getBoundingClientRect().top-120)
            )""")
            page.wait_for_timeout(1000)
            if not headline_visible_in_viewport(h.bounding_box(),page.viewport_size):
                return {"ok":False,"reason":"publisher_h1_outside_frame"}
            if not original_article_images_loaded(page):
                return {"ok":False,"reason":"original_article_image_not_loaded"}
            result=capture_verified_original_frame(
                page,publisher,dest,requested_url=original,headline=h)
            return result
        finally:
            browser.close()
