"""Public-publisher screenshot guardrails. No private RASD code or credentials.

This is a visual-content heuristic, not proof that a page's claims are true.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image, ImageStat, UnidentifiedImageError

# Only reviewed public news publishers used in this test-only worker.
APPROVED_PUBLISHERS = {
    "hapijournal.com": frozenset({"hapijournal.com", "www.hapijournal.com"}),
    "elwatannews.com": frozenset({"elwatannews.com", "www.elwatannews.com"}),
    "almasryalyoum.com": frozenset({"almasryalyoum.com", "www.almasryalyoum.com"}),
}
CHALLENGE_WORDS = (
    "verify you are human", "just a moment...", "checking your browser",
    "captcha", "access denied",
)


def allowed_url(url: str, publisher: str, *, asset: bool = False) -> bool:
    """Disallow IPs, unrelated origins, non-TLS schemes and unusual ports."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (publisher not in APPROVED_PUBLISHERS
                or parsed.scheme != "https"
                or parsed.port not in (None, 443)
                or parsed.username or parsed.password):
            return False
        if asset:
            return host == publisher or host.endswith("." + publisher)
        return host in APPROVED_PUBLISHERS[publisher]
    except (ValueError, TypeError, AttributeError):
        return False


def image_quality(path: Path) -> dict:
    """Detect near-blank browser frames without OCR or external AI."""
    try:
        with Image.open(path) as photo:
            if photo.width < 600 or photo.height < 400:
                return {"accepted": False, "reason": "too_small_dimensions"}
            gray = photo.convert("L").resize((240, 180))
            stddev = ImageStat.Stat(gray).stddev[0]
            hist = gray.histogram()
            dark_fraction = sum(hist[:180]) / (240 * 180)
            valid = stddev >= 12.0 and dark_fraction >= 0.01
            return {"accepted": valid,
                    "reason": "ok" if valid else "blank_or_low_content",
                    "luminance_stddev": round(stddev, 2),
                    "dark_fraction": round(dark_fraction, 4)}
    except (OSError, ValueError, UnidentifiedImageError):
        return {"accepted": False, "reason": "invalid_image"}


def capture_publisher(url: str, publisher: str, destination: Path,
                      timeout_ms: int = 26000) -> dict:
    """Capture only a publicly published article within an approved publisher."""
    if not allowed_url(url, publisher):
        return {"ok": False, "reason": "publisher_not_approved"}
    destination = Path(destination)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                context = browser.new_context(
                    viewport={"width": 1200, "height": 900}, locale="ar-EG",
                    device_scale_factor=1, accept_downloads=False,
                    service_workers="block", ignore_https_errors=False)
                context.route("**/*", lambda route: (
                    route.continue_() if allowed_url(route.request.url, publisher, asset=True)
                    else route.abort()))
                page = context.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if response is None or not 200 <= response.status < 400:
                    return {"ok": False, "reason": "publisher_http_failure"}
                if not allowed_url(page.url, publisher):
                    return {"ok": False, "reason": "redirect_outside_publisher"}
                title = page.title()
                body = page.locator("body").inner_text(timeout=10000).strip()
                if len(body) < 180 or any(word in body[:1800].lower() for word in CHALLENGE_WORDS):
                    return {"ok": False, "reason": "page_content_unavailable"}
                if "التخطيط" not in (title + " " + body) and "planning" not in (title + " " + body).lower():
                    return {"ok": False, "reason": "not_a_planning_article"}
                page.wait_for_timeout(1300)
                destination.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(destination), type="jpeg",
                                quality=80, full_page=False, timeout=15000)
                if destination.stat().st_size < 8000:
                    destination.unlink(missing_ok=True)
                    return {"ok": False, "reason": "screenshot_too_small"}
                quality = image_quality(destination)
                if not quality["accepted"]:
                    destination.unlink(missing_ok=True)
                    return {"ok": False, "reason": "visual_qa_" + quality["reason"],
                            "quality": quality}
                raw = destination.read_bytes()
                if not raw.startswith(bytes((0xFF, 0xD8))):
                    destination.unlink(missing_ok=True)
                    return {"ok": False, "reason": "invalid_jpeg_signature"}
                return {"ok": True, "reason": "accepted",
                        "actual_url": page.url, "title": title[:300],
                        "http_status": response.status,
                        "image": destination.name, "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "quality": quality}
            finally:
                browser.close()
    except Exception as exc:
        # Keep the network/browser error in the audit; never claim a capture.
        destination.unlink(missing_ok=True)
        return {"ok": False, "reason": type(exc).__name__}
