"""Optional original-platform post screenshot capture for a RASD REVIEW.

Playwright is never imported unless owner-authorized. No login, cookies,
sessions, screenshot substitutions, or bypass. The browser must show original
post text and account on the EXACT original permalink; otherwise HOLD.
DOM matching is provisional identity evidence, NOT a fact-check.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from rasd_four_reports_review import _url

MAX_IMAGE = 8_000_000


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def _identity_visible(visible: str, *, message: str, source: str,
                      platform: str) -> bool:
    tokens = _normalize(message).split()
    if len(tokens) < 4:
        return False
    # Distinct matched text words and source/account appear in same post.
    excerpt = " ".join(tokens[:min(7, len(tokens))])
    if excerpt not in _normalize(visible):
        return False
    if platform == "x":
        return source.casefold().lstrip("@") in visible.casefold()
    return bool(_normalize(source) and
                _normalize(source) in _normalize(visible))


def capture_original_post(candidate: dict, destination: Path, *,
                          browser_factory=None,
                          owner_authorized: bool = False) -> dict:
    """Fetch original permalink and screenshot matching post only. FAIL CLOSED."""
    if not owner_authorized:
        return {"status": "hold", "reason": "social_capture_not_authorized"}
    platform = candidate.get("platform")
    if platform not in ("facebook", "x", "instagram"):
        return {"status": "hold", "reason": "social_capture_platform_hold"}
    try:
        url = _url(candidate.get("url"), "social", platform)
        message = candidate["text"]
        source = candidate["source"]
        ident = candidate["platform_post_id"]
        if (not isinstance(message, str) or not isinstance(source, str)
                or not isinstance(ident, str)):
            raise ValueError
        if not destination.parent.is_dir() or destination.suffix.lower() != ".png":
            raise ValueError
        if browser_factory is None:
            from playwright.sync_api import sync_playwright
            browser_factory = sync_playwright
        # Browser factory is an isolated test seam, not an origin-trust proof.
        with browser_factory() as engine:
            browser = engine.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 1100, "height": 900},
                    locale="ar-EG", service_workers="block")
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=18000)
                    page.wait_for_timeout(1100)
                    actual = urlsplit(page.url)
                    required = urlsplit(url)
                    if (actual.scheme != "https" or
                            actual.hostname != required.hostname or
                            actual.path.rstrip("/") != required.path.rstrip("/")):
                        raise ValueError("social_original_redirect_hold")
                    if platform == "x":
                        cards = page.locator("article")
                    elif platform == "instagram":
                        cards = page.locator('article, [role="article"]')
                    else:
                        cards = page.locator('[role="article"]')
                    count = min(cards.count(), 25)
                    candidate_card = None
                    for n in range(count):
                        card = cards.nth(n)
                        if _identity_visible(
                                card.inner_text(timeout=3000),
                                message=message, source=source,
                                platform=platform):
                            candidate_card = card
                            break
                    if candidate_card is None:
                        raise ValueError("social_original_post_not_visible_hold")
                    image = candidate_card.screenshot(timeout=10000)
                    if len(image) > MAX_IMAGE:
                        raise ValueError("social_original_image_size_hold")
                    destination.write_bytes(image)
                    with Image.open(destination) as picture:
                        if (picture.format != "PNG" or picture.width < 200
                                or picture.height < 120):
                            raise ValueError("social_original_image_invalid_hold")
                        picture.verify()
                    return {
                        "status": "verified", "method": "authorized_platform_original_capture",
                        "url": url, "platform_post_id": ident,
                        "sha256": hashlib.sha256(image).hexdigest(),
                    }
                finally:
                    context.close()
            finally:
                browser.close()
    except Exception:
        # Includes Playwright navigation/timeout errors; never log page content.
        destination.unlink(missing_ok=True)
        return {"status": "hold", "reason": "social_original_capture_unavailable"}
