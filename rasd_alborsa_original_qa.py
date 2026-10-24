"""Read-only GitHub-hosted ORIGINAL Alborsa publisher page capture probe.

Historical published Oct 23 news article. No Gmail, private ledger, artifact
uploads, article substitution, or claims that this is current-day coverage.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright

from capture_public import image_quality

ORIGINAL_URL = "https://www.alborsaanews.com/2026/10/23/2001360"
ACCEPTED_HOSTS = {"www.alborsaanews.com", "alborsaanews.com"}


def result(label: str, **details):
    print("RASD_ALBORSA_ORIGINAL_QA=" +
          json.dumps({"status": label, "no_email": True,
                      "source_scope": "HISTORICAL_ORIGINAL_ONLY", **details},
                     ensure_ascii=False, sort_keys=True), flush=True)


def permitted(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and
                parsed.hostname in ACCEPTED_HOSTS and
                not parsed.username and not parsed.password and
                not parsed.port)
    except ValueError:
        return False


def main():
    with tempfile.TemporaryDirectory(prefix="rasd-original-borsa-") as temp:
        out = Path(temp) / "publisher-original.jpg"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                context = browser.new_context(
                    viewport={"width":1200,"height":900},
                    locale="ar-EG", service_workers="block",
                    accept_downloads=False, ignore_https_errors=False)
                context.route("**/*", lambda route: (
                    route.continue_() if permitted(route.request.url)
                    else route.abort()))
                page = context.new_page()
                response = page.goto(ORIGINAL_URL,
                                     wait_until="domcontentloaded",
                                     timeout=25000)
                if response is None:
                    result("HOLD_NO_PUBLISHER_RESPONSE")
                    return
                status = response.status
                if status != 200 or page.url != ORIGINAL_URL:
                    result("HOLD_PUBLISHER_REFUSED_OR_REDIRECTED",
                           http_status=status)
                    return
                body = page.locator("body").inner_text(timeout=9000)
                title = page.locator("h1").first
                if title.count() == 0:
                    result("HOLD_NO_ORIGINAL_HEADLINE")
                    return
                headline = " ".join(title.inner_text(timeout=7000).split())
                if (len(headline) < 18 or "التخطيط" not in headline or
                        "التخطيط" not in body or len(body) < 200):
                    result("HOLD_PUBLISHER_TEXT_NOT_VERIFIED")
                    return
                title.scroll_into_view_if_needed(timeout=5000)
                title.evaluate(
                    """element => window.scrollTo(
                         0, Math.max(0, window.scrollY +
                            element.getBoundingClientRect().top - 110))""")
                page.wait_for_timeout(400)
                box = title.bounding_box()
                if (not box or box["width"] < 250 or
                        not 0 <= box["y"] < 460):
                    result("HOLD_ORIGINAL_TITLE_NOT_VISIBLE")
                    return
                page.screenshot(path=str(out),type="jpeg", quality=83,
                                full_page=False,timeout=15000)
                quality = image_quality(out)
                with Image.open(out) as im:
                    dimensions = list(im.size)
                if not quality["accepted"]:
                    result("HOLD_ORIGINAL_SCREENSHOT_VISUAL_QA",
                           dimensions=dimensions)
                    return
                digest = hashlib.sha256(out.read_bytes()).hexdigest()
                result("VERIFIED_ONE_ORIGINAL_NEWSROOM_SCREENSHOT",
                       http_status=status, image_bytes=out.stat().st_size,
                       dimensions=dimensions, sha256=digest,
                       article_id="original-alborsa-2026-10-23-2001360")
            finally:
                browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Predefined exception type only; never expose page HTML or secrets.
        result("HOLD_ORIGINAL_CLOUD_BROWSER_EXCEPTION",
               exception_type=type(exc).__name__)
