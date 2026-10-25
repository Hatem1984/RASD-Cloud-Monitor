"""Public-publisher screenshot guardrails. No private RASD code or credentials.

This is a visual-content heuristic, not proof that a page's claims are true.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from PIL import Image, ImageStat, UnidentifiedImageError

# Only reviewed public news publishers used in this test-only worker.
APPROVED_PUBLISHERS = {
    "gomhuriaonline.com": frozenset({"almessa.gomhuriaonline.com"}),
    "elbalad.news": frozenset({"www.elbalad.news"}),
    "vetogate.com": frozenset({"www.vetogate.com"}),
    "dailynewsegypt.com": frozenset({"www.dailynewsegypt.com"}),
    "egyptindependent.com": frozenset({"www.egyptindependent.com"}),
    "egyptianstreets.com": frozenset({"egyptianstreets.com"}),
    "skynewsarabia.com": frozenset({"www.skynewsarabia.com"}),
    "inp.edu.eg": frozenset({"inp.edu.eg"}),
    "hapijournal.com": frozenset({"hapijournal.com", "www.hapijournal.com"}),
    "elwatannews.com": frozenset({"elwatannews.com", "www.elwatannews.com"}),
    "almasryalyoum.com": frozenset({"almasryalyoum.com", "www.almasryalyoum.com"}),
    "shorouknews.com": frozenset({"www.shorouknews.com"}),
    "alborsaanews.com": frozenset({"alborsaanews.com", "www.alborsaanews.com"}),
    "masrawy.com": frozenset({"www.masrawy.com", "masrawy.com"}),
}
# An official Ministry programme may be named without the word "planning".
# These exact topics preserve the narrow ministry brief and exclude generic economy news.
PLANNING_TOPIC_NAMES = (
    "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
    "التخطيط والتنمية الاقتصادية", "معهد التخطيط القومي",
    "Ministry of Planning", "Planning Ministry",
    "البرنامج الوطني للتحول الاقتصادي",
    "السردية الوطنية للتنمية الاقتصادية",
    "المبادرة الوطنية للمشروعات الخضراء الذكية",
    "المراجعة الوطنية الطوعية لمصر",
    "تقرير مصر الوطني الطوعي",
    "المنظومة المتكاملة للتخطيط التنموي",
    "الخطة الاستثمارية للدولة",
    "National Planning Institute",
    "Ministry of Planning and Economic Development",
    "Egyptian Ministry of Planning",
)


def is_planning_publisher_page(title: str, body: str) -> bool:
    """Match only the owner's saved official planning terms on a publisher page."""
    if not isinstance(title, str) or not isinstance(body, str):
        return False
    from monitor import _ministry_term_present
    return _ministry_term_present(title + " " + body, list(PLANNING_TOPIC_NAMES))


CHALLENGE_WORDS = (
    "verify you are human", "just a moment...", "checking your browser",
    "captcha", "access denied",
)


def classify_publisher_http_status(status: int | None) -> str:
    """A fixed diagnostic code only: no raw response bodies or website text."""
    if status is None:
        return "publisher_no_http_response"
    if status in (401, 403):
        return "publisher_access_refused"
    if status == 404 or status == 410:
        return "publisher_article_unavailable"
    if status == 429:
        return "publisher_rate_limited"
    if 500 <= status <= 599:
        return "publisher_server_error"
    return "publisher_http_failure"


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


def suspicious_flat_lead_media(photo: Image.Image) -> bool:
    """Conservative fail-closed clue for an unloaded giant publisher photo.

    Genuine live evidence showed a uniformly grey 1200x900 publisher-page
    hero occupying the main central left article area, while the headline
    and ads kept the *whole* screenshot visually nonblank. Browser img
    load-state checks can miss CSS/lazy/background placeholders.
    This is a heuristic HOLD, never proof of deliberate publisher failure;
    it neither edits screenshot pixels nor substitutes any photo.
    """
    width, height = photo.size
    if width < 900 or height < 700:
        return False
    lead = photo.convert("RGB").crop((
        int(width * 0.05), int(height * 0.42),
        int(width * 0.63), int(height * 0.78),
    ))
    lead.thumbnail((160, 100))
    stats = ImageStat.Stat(lead)
    means, deviations = stats.mean, stats.stddev
    return (230 <= min(means) and max(means) <= 252
            and max(means) - min(means) <= 2.8
            and max(deviations) <= 2.4)


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
            flat_lead = suspicious_flat_lead_media(photo) if valid else False
            reason = ("blank_or_low_content" if not valid else
                      "suspicious_flat_original_lead_media" if flat_lead else "ok")
            return {"accepted": valid and not flat_lead,
                    "reason": reason,
                    "luminance_stddev": round(stddev, 2),
                    "dark_fraction": round(dark_fraction, 4)}
    except (OSError, ValueError, UnidentifiedImageError):
        return {"accepted": False, "reason": "invalid_image"}


def accept_staged_image(staged: Path, destination: Path) -> dict:
    """Commit a newly captured JPEG only after passing all visual checks.

    Validation errors never overwrite an existing screenshot at destination.
    Staging files are caller-owned and may be discarded on failure.
    """
    if staged.stat().st_size < 8000:
        return {"ok": False, "reason": "screenshot_too_small"}
    quality = image_quality(staged)
    if not quality["accepted"]:
        return {"ok": False, "reason": "visual_qa_" + quality["reason"],
                "quality": quality}
    raw = staged.read_bytes()
    if not raw.startswith(bytes((0xFF, 0xD8))):
        return {"ok": False, "reason": "invalid_jpeg_signature"}
    staged.replace(destination)
    return {"ok": True, "reason": "accepted",
            "image": destination.name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "quality": quality}


def headline_visible_in_viewport(box: dict | None, viewport: dict | None) -> bool:
    """Visual frame must contain real, readable publisher headline geometry."""
    try:
        if not box or not viewport:
            return False
        width, height = viewport["width"], viewport["height"]
        return (900 <= width <= 1500 and height >= 700 and
                0 <= box["x"] and box["x"] + box["width"] <= width + 8 and
                55 <= box["y"] <= min(460, height - 200) and
                box["width"] >= 320 and box["height"] >= 16)
    except (KeyError, ValueError, TypeError):
        return False



def visible_article_image_missing(rows: list[dict]) -> bool:
    """Never accept a prominent publisher article photo that did not load.

    The browser supplies geometry and native image load state from the
    untouched original page. This is not a substitute photo or a bypass.
    Missing images outside the screenshot viewport are irrelevant.
    """
    if not isinstance(rows, list):
        return True
    for row in rows:
        if (not isinstance(row, dict) or
                type(row.get("visible")) is not bool or
                type(row.get("loaded")) is not bool):
            return True
        if row["visible"] and not row["loaded"]:
            return True
    return False


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
                    return {"ok": False, "reason": classify_publisher_http_status(
                        None if response is None else response.status)}
                if not allowed_url(page.url, publisher):
                    return {"ok": False, "reason": "redirect_outside_publisher"}
                title = page.title()
                body = page.locator("body").inner_text(timeout=10000).strip()
                if len(body) < 180 or any(word in body[:1800].lower() for word in CHALLENGE_WORDS):
                    return {"ok": False, "reason": "page_content_unavailable"}
                if not is_planning_publisher_page(title, body):
                    return {"ok": False, "reason": "not_a_planning_article"}
                # Scroll the ORIGINAL publisher page so its genuine H1
                # and article lead, not a large ad masthead, fill the
                # screenshot. Never alter DOM text, source or access rights.
                headline = page.locator("h1").first
                if not headline.count():
                    return {"ok": False, "reason": "missing_original_headline"}
                actual_headline = " ".join(
                    headline.inner_text(timeout=8000).split())
                if (len(actual_headline) < 18 or
                        actual_headline not in " ".join(body.split())):
                    return {"ok": False, "reason": "original_headline_not_in_article"}
                headline.scroll_into_view_if_needed(timeout=4000)
                headline.evaluate(
                    """element => window.scrollTo(
                        0, Math.max(0, window.scrollY +
                           element.getBoundingClientRect().top - 120)
                    )""")
                # Lazy article media gets a bounded opportunity to load
                # from the already-approved publisher origin. No outside CDN,
                # retry of a 401/403, DOM alteration or generated replacement.
                page.wait_for_timeout(1600)
                if not headline_visible_in_viewport(
                        headline.bounding_box(), page.viewport_size):
                    return {"ok": False, "reason": "original_headline_out_of_frame"}
                photo_states = page.evaluate("""() => {
                    const imgs = document.querySelectorAll(
                        'article img, .entry-content img, .post-content img, .article-content img');
                    return Array.from(imgs).map(img => {
                        const r = img.getBoundingClientRect();
                        const style = getComputedStyle(img);
                        const visible = r.width >= 300 && r.height >= 150 &&
                            r.bottom > 0 && r.top < innerHeight &&
                            r.right > 0 && r.left < innerWidth &&
                            style.visibility !== 'hidden' &&
                            style.display !== 'none';
                        return {visible: visible,
                                loaded: img.complete && img.naturalWidth >= 80};
                    });
                }""")
                if visible_article_image_missing(photo_states):
                    return {"ok": False, "reason": "original_article_image_not_loaded"}
                destination.parent.mkdir(parents=True, exist_ok=True)
                with TemporaryDirectory(prefix=".rasd-capture-", dir=destination.parent) as temp:
                    staged = Path(temp) / "candidate.jpg"
                    page.screenshot(path=str(staged), type="jpeg",
                                    quality=80, full_page=False, timeout=15000)
                    accepted = accept_staged_image(staged, destination)
                if not accepted["ok"]:
                    return accepted
                return {**accepted, "actual_url": page.url,
                        "title": title[:300], "http_status": response.status}
            finally:
                browser.close()
    except Exception as exc:
        # Only fresh, fully validated files are promoted to destination.
        return {"ok": False, "reason": type(exc).__name__}
