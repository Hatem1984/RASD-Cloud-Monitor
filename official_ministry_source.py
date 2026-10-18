"""Opt-in Gate 38 official Ministry source qualification; NEVER production send.

Publisher website may serve article pages while its listing is unavailable.
Preserve that distinction: a reviewed example link is not automatic discovery.
No third-party search, ID enumeration, credentials, public Word/JPEG or cron.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from capture_public import CHALLENGE_WORDS, accept_staged_image
from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from monitor import _ministry_term_present, article_id

CAIRO = ZoneInfo("Africa/Cairo")
INDEX = "https://mped.gov.eg/News?id=57&lang=ar"
# A PUBLISHED/INDEPENDENTLY REVIEWED ORIGINAL-PAGE URL, not a discovery feed.
SAMPLE = "https://mped.gov.eg/singlenews?id=7269&lang=ar"
OFFICIAL_HOSTS = frozenset(("mped.gov.eg", "www.mped.gov.eg"))
MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8,
    "سبتمبر": 9, "أكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def canonical_official_article(url: str) -> str | None:
    try:
        p = urlsplit(url)
        if (p.scheme != "https" or p.hostname not in OFFICIAL_HOSTS
                or p.port not in (None, 443) or p.username or p.password
                or p.path.casefold() != "/singlenews" or p.fragment):
            return None
        query = parse_qs(p.query, keep_blank_values=True, strict_parsing=True)
        if set(query) != {"id", "lang"} or any(len(v) != 1 for v in query.values()):
            return None
        ident = query["id"][0]
        if (not re.fullmatch(r"[1-9][0-9]{0,8}", ident)
                or query["lang"][0] != "ar"):
            return None
        return f"https://mped.gov.eg/singlenews?id={ident}&lang=ar"
    except (ValueError, TypeError, AttributeError):
        return None


def allowed_official_resource(url: str) -> bool:
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in OFFICIAL_HOSTS
                and p.port in (None, 443) and not p.username and not p.password)
    except (ValueError, TypeError, AttributeError):
        return False


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "a":
            target = dict(attrs).get("href")
            if target:
                self.hrefs.append(target)


def index_articles(html: str) -> list[str]:
    if not isinstance(html, str) or len(html) > 1_500_000:
        raise ValueError("official_index_size_invalid")
    parser = _Links()
    parser.feed(html)
    found = {}
    for raw in parser.hrefs[:500]:
        url = canonical_official_article(urljoin(INDEX, raw))
        if url:
            found[url] = None
    return list(found)[:35]


def original_publication_date(body: str, headline: str) -> date | None:
    """Read date adjacent to article headline, not crawl time or footer date."""
    if not isinstance(body, str) or not isinstance(headline, str):
        return None
    title = " ".join(headline.split())
    normalized = " ".join(body.split())
    at = normalized.find(title)
    if at < 0:
        return None
    # Date must be close to original article heading; no nav/footer inference.
    nearby = normalized[at + len(title):at + len(title) + 280]
    pattern = r"(?<!\d)([0-9٠-٩]{1,2})\s+(" + "|".join(MONTHS) + r")\s+([0-9٠-٩]{4})(?!\d)"
    dates = re.findall(pattern, nearby)
    if len(dates) != 1:
        return None
    dd, mm, yy = dates[0]
    try:
        parsed = date(int(yy.translate(ARABIC_DIGITS)),
                      MONTHS[mm], int(dd.translate(ARABIC_DIGITS)))
        return parsed if 2020 <= parsed.year <= 2100 else None
    except ValueError:
        return None


def _read_original(page, url: str, keywords: list[str], target_day: date, image: Path):
    """All original-page checks occur on the SAME browser-rendered page."""
    if canonical_official_article(url) != url:
        return {"status": "HOLD", "reason": "invalid_article_url"}
    response = page.goto(url, wait_until="domcontentloaded", timeout=24000)
    if response is None or response.status != 200:
        return {"status": "HOLD", "reason": "publisher_page_unavailable"}
    if canonical_official_article(page.url) != url:
        return {"status": "HOLD", "reason": "publisher_redirect_changed_identity"}
    headline = " ".join(page.locator("h1").first.inner_text(timeout=8000).split())
    if len(headline) < 16 or len(headline) > 350:
        return {"status": "HOLD", "reason": "missing_original_headline"}
    body = page.locator("body").inner_text(timeout=8000)
    if (len(body) < 350 or len(body) > 500_000 or
            any(mark in body[:2000].lower() for mark in CHALLENGE_WORDS)):
        return {"status": "HOLD", "reason": "official_page_content_unavailable"}
    if not _ministry_term_present(headline, keywords):
        return {"status": "HOLD", "reason": "saved_ministry_keywords_missing"}
    published = original_publication_date(body, headline)
    if published is None or published != target_day:
        return {"status": "HOLD", "reason": "publisher_date_mismatch_or_missing"}
    image.parent.mkdir(parents=True, exist_ok=True)
    try:
        page.locator("h1").first.scroll_into_view_if_needed(timeout=4000)
    except Exception:
        return {"status": "HOLD", "reason": "original_headline_not_visible"}
    with tempfile.TemporaryDirectory(prefix="rasd-official-frame-", dir=image.parent) as td:
        staged = Path(td) / "publisher.jpg"
        page.screenshot(path=str(staged), type="jpeg", quality=82,
                        full_page=False, timeout=15000)
        proof = accept_staged_image(staged, image)
    if not proof["ok"]:
        return {"status": "HOLD", "reason": proof["reason"]}
    return {
        "status": "verified", "url": url, "id": article_id(url),
        "headline": headline, "published_date_cairo": published.isoformat(),
        "sha256": proof["sha256"], "image_path": str(image),
    }


def run(*, config_path=Path("sources.json"), target_day=date(2026, 10, 17),
        sample_url=SAMPLE, listing_url=INDEX) -> dict:
    """Read-only acceptance probe, no Word or image survives temp cleanup."""
    if (type(target_day) is not date or listing_url != INDEX or
            sample_url != SAMPLE or canonical_official_article(sample_url) != sample_url):
        raise ValueError("official_test_scope_unapproved")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (config.get("keywords") != [
        "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
        "التخطيط والتنمية الاقتصادية"
    ] or [x.get("id") for x in config.get("feeds", [])] != [
        "hapi", "almasryalyoum"
    ]):
        raise ValueError("official_test_saved_profile_changed")
    output = {
        "mode": "official_ministry_optin_qa",
        "official_index": "HOLD", "index_article_links": 0,
        "sample_origin": "separately_reviewed_original_url_NOT_feed_discovery",
        "sample_status": "HOLD", "sample_verified_screenshots": 0,
        "sample_word_images_verified": False,
        "sample_publication_date_cairo": None,
        "production_feed_changed": False, "keywords_changed": False,
        "source_added_to_production": False, "final_report_published": False,
        "email_sent": False, "scheduler_enabled": False,
        "private_archive_used": False,
    }
    try:
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix="rasd-official-qa-") as temp:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                try:
                    context = browser.new_context(
                        viewport={"width": 1200, "height": 900}, locale="ar-EG",
                        ignore_https_errors=False, accept_downloads=False,
                        service_workers="block")
                    context.route("**/*", lambda route: (
                        route.continue_() if allowed_official_resource(route.request.url)
                        else route.abort()))
                    page = context.new_page()
                    try:
                        response = page.goto(
                            listing_url, wait_until="domcontentloaded", timeout=24000)
                        if response is not None and response.status == 200:
                            page.wait_for_timeout(1500)
                            links = index_articles(page.content())
                            output["index_article_links"] = len(links)
                            output["official_index"] = "FOUND" if links else "HOLD"
                    except Exception:
                        output["index_failure"] = "unavailable_or_unreadable"
                    image = Path(temp) / "verified.jpg"
                    # A known publisher story proves READ/CAPTURE, not discovery.
                    try:
                        receipt = _read_original(
                            page, sample_url, config["keywords"], target_day, image)
                    except Exception:
                        receipt = {"status": "HOLD", "reason": "original_page_probe_failed"}
                    output["sample_status"] = receipt["status"]
                    if receipt["status"] == "verified":
                        output["sample_publication_date_cairo"] = receipt["published_date_cairo"]
                        output["sample_verified_screenshots"] = 1
                        report = {
                            "title": "رصد | اختبار صفحة أصلية رسمية — ليس التقرير النهائي",
                            "display_window_start": "17 أكتوبر 2026",
                            "display_window_end": "17 أكتوبر 2026",
                            "coverage": "OFFICIAL_SOURCE_QA_ONLY",
                            "verified_links": 1, "articles": [{
                                "headline": receipt["headline"],
                                "source": "وزارة التخطيط — الموقع الرسمي",
                                "url": receipt["url"],
                                "published_at_cairo": "2026-10-17 (date only)",
                                "published_display_cairo": "17 أكتوبر 2026 — بدون ساعة منشورة",
                                "evidence_image_path": receipt["image_path"],
                            }],
                            "sources": [{"feed_id": "mped-official",
                                         "status": "ok", "verified_links": 1,
                                         "error_type": None}],
                            "limitations": "اختبار رابط معروف مسبقًا وليس اكتشافًا آليًا أو تقرير إنتاج.",
                        }
                        word = Path(temp) / "official-qa.docx"
                        render_docx(report, word)
                        output["sample_word_images_verified"] = (
                            word_images_match_capture_digests(
                                word, [{"status": "verified", "sha256": receipt["sha256"]}]))
                        if not output["sample_word_images_verified"]:
                            output["sample_status"] = "HOLD"
                    else:
                        output["sample_failure"] = receipt.get("reason", "other")
                finally:
                    browser.close()
    except Exception:
        output["probe_failure"] = "browser_or_publisher_unavailable"
    output["status"] = (
        "READY_SOURCE_QA_ONLY" if (
            output["official_index"] == "FOUND" and
            output["sample_status"] == "verified" and
            output["sample_word_images_verified"]) else "HOLD"
    )
    return output


if __name__ == "__main__":
    try:
        print(json.dumps(run(), ensure_ascii=False, sort_keys=True), flush=True)
    except Exception:
        print("official_ministry_probe_held; no publish or mail", flush=True)
        raise SystemExit(2) from None
