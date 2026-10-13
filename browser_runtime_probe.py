"""Isolated Playwright screenshot engine health check, never a news capture.

The page is generated locally in memory. No external host is contacted.
A passing result proves Chromium, JPEG output and image QA work on this runner;
it must NOT be presented as a real publisher screenshot.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from capture_public import image_quality


def main() -> None:
    from playwright.sync_api import sync_playwright

    # This is a synthetic fixture; NEVER insert its image into a news report.
    rows = "".join('<p class="line">Offline browser renderer health check</p>' for _ in range(12))
    markup = (
        '<html lang="en"><head><meta charset="utf-8"><style>'
        'body{background:#fff;font:20px Arial;margin:0;}'
        'header{background:#172c41;color:#fff;padding:38px 48px;}'
        'main{padding:28px 48px}.line{border-bottom:3px solid #566878;'
        'padding:6px 0;color:#1d324b;}'
        '</style></head><body><header><h1>RASD Offline Browser Test</h1>'
        '</header><main>' + rows + '</main></body></html>'
    )
    with tempfile.TemporaryDirectory(prefix="rasd-browser-qa-") as temp:
        path = Path(temp) / "synthetic-not-news.jpg"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1200, "height": 900},
                    accept_downloads=False, service_workers="block",
                )
                context.route("**/*", lambda route: route.abort())
                page = context.new_page()
                page.set_content(markup, wait_until="load")
                page.screenshot(path=str(path), type="jpeg", quality=80, full_page=False)
            finally:
                browser.close()
        quality = image_quality(path)
        if not quality["accepted"] or path.stat().st_size < 8000:
            raise RuntimeError("offline_screenshot_engine_failed")
    # Keep output strictly factual: synthetic output is never publication evidence.
    print(json.dumps({
        "kind": "synthetic_offline_browser_qa",
        "chromium_screenshot_engine_ok": True,
        "real_publisher_screenshot_verified": False,
        "email_sent": False,
        "scheduler_enabled": False,
    }), flush=True)


if __name__ == "__main__":
    main()
