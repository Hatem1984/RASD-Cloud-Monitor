"""Gate 40: one source-bound Ministry Word QA, no mail, private archive or cron.

Single date-scoped report merges two existing native RSS publishers with the
official Ministry's ORIGINAL NewsList (real card IDs, no guesses). Every
included article MUST have a verified original publisher-page JPEG and an
identical DOCX drawing. A failed selected article holds the WHOLE report.
The official connector stays opt-in; production sources.json is unchanged.
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from cloud_proof_report import proof_capture, word_images_match_capture_digests
from daily_report import CAIRO, MAX_ARTICLES, cairo_display_time, render_docx
from gate11_runner import candidate_from_feed
from monitor import _ministry_term_present, article_id, inspect, read_feed
from official_ministry_source import (
    _read_original, allowed_official_resource, canonical_official_article,
    discover_official_newslist, original_publication_date,
)

OFFICIAL_NAME = "وزارة التخطيط — الموقع الرسمي"


class OfficialPageDriver:
    """Genuine isolated Chromium source reader: one browser, same domain."""
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        try:
            self.browser = self.pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            self.context = self.browser.new_context(
                viewport={"width": 1200, "height": 900}, locale="ar-EG",
                ignore_https_errors=False, accept_downloads=False,
                service_workers="block")
            self.context.route("**/*", lambda route: (
                route.continue_() if allowed_official_resource(route.request.url)
                else route.abort()))
            self.page = self.context.new_page()
        except Exception:
            self.pw.stop()
            raise
        return self

    def __exit__(self, *_):
        try:
            self.browser.close()
        finally:
            self.pw.stop()

    def discover(self):
        return discover_official_newslist(self.context.request)

    def inspect(self, url: str, *, keywords: list[str],
                target_day: date, image: Path) -> dict:
        if canonical_official_article(url) != url:
            return {"status": "HOLD", "reason": "official_url_invalid"}
        try:
            response = self.page.goto(
                url, wait_until="domcontentloaded", timeout=24000)
            if response is None or response.status != 200:
                return {"status": "HOLD", "reason": "official_article_unavailable"}
            if canonical_official_article(self.page.url) != url:
                return {"status": "HOLD", "reason": "official_article_redirect"}
            headline = " ".join(
                self.page.locator("h1").first.inner_text(timeout=8000).split())
            body = self.page.locator("body").inner_text(timeout=8000)
            if not 16 <= len(headline) <= 350 or not 350 <= len(body) <= 500_000:
                return {"status": "HOLD", "reason": "official_content_unavailable"}
            published = original_publication_date(body, headline)
            if published is None:
                return {"status": "HOLD", "reason": "official_publication_day_missing"}
            if published != target_day:
                return {"status": "OUT_OF_WINDOW"}
            if not _ministry_term_present(headline, keywords):
                return {"status": "EXCLUDED_NON_MATCHING_TERM"}
            proof = _read_original(self.page, url, keywords, target_day, image)
            if proof["status"] != "verified":
                return {"status": "HOLD", "reason": proof.get("reason", "capture_failed")}
            return {
                "status": "verified", "id": proof["id"], "url": url,
                "headline": proof["headline"],
                "published_date_cairo": proof["published_date_cairo"],
                "sha256": proof["sha256"],
            }
        except Exception:
            return {"status": "HOLD", "reason": "official_page_validation_failed"}


def _validate_profile(config: dict) -> None:
    # Strict operational migration gate; release of generic profiles is
    # separate future work, not an unintended modification in Stage 2.
    if config.get("scope") != "Egyptian Ministry of Planning - publicly published news only":
        raise ValueError("unified_ministry_scope_changed")
    if config.get("keywords") != [
        "وزارة التخطيط", "وزير التخطيط",
        "وزيرة التخطيط", "التخطيط والتنمية الاقتصادية",
    ]:
        raise ValueError("unified_saved_keywords_changed")
    if [x.get("id") for x in config.get("feeds", [])] != [
        "hapi", "almasryalyoum",
    ]:
        raise ValueError("unified_publisher_feeds_changed")


def build_unified_word(
    config_path: Path,
    output_dir: Path,
    *,
    target_day: date,
    now: datetime | None = None,
    fetch=read_feed,
    official_driver_factory=OfficialPageDriver,
    capture=None,
) -> dict:
    """Emit final Word *only* if all source, date, JPEG and DOCX checks pass.

    target_day must be today or yesterday Cairo; an old snapshot requires a
    distinct historical archive qualification and is never treated as full
    current-source coverage. Does not attempt a historical '25' quota.
    """
    checked = datetime.now(timezone.utc) if now is None else now
    if checked.tzinfo is None or checked.utcoffset() is None:
        raise ValueError("unified_clock_must_be_aware")
    checked = checked.astimezone(CAIRO)
    if type(target_day) is not date or target_day not in (
        checked.date(), checked.date() - timedelta(days=1),
    ):
        raise ValueError("unified_day_outside_safe_window")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    _validate_profile(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    word_path = output_dir / f"RASD-Unified-{target_day.isoformat()}.docx"
    word_path.unlink(missing_ok=True)  # stale successful report must not survive HOLD

    result = {
        "mode": "stage2_ministry_unified_word_ephemeral_qa",
        "target_date_cairo": target_day.isoformat(),
        "status": "HOLD", "coverage": "DEGRADED",
        "rss_source_count": 2, "official_source_count": 1,
        "rss_matched_on_day": 0, "official_index_urls": 0,
        "official_same_day": 0, "official_offday": 0,
        "selected_unique_articles": 0,
        "screenshots_verified": 0, "screenshots_missing": 0,
        "word_created": False, "word_images_verified": False,
        "all_sources_healthy": False,
        "failures": {}, "source_health": [],
        "first_page_official_scope_only": True,
        "date_only_official_not_assigned_hour": True,
        "production_sources_changed": False, "keywords_changed": False,
        "source_added_to_production": False, "final_report_published": False,
        "email_sent": False, "scheduler_enabled": False,
        "private_storage_used": False,
    }
    reasons = {}
    def hold(reason):
        reasons[reason] = reasons.get(reason, 0) + 1
    # Only SOURCE ID/count and allowlisted reason labels appear in public logs.
    inspected = inspect(config, fetch=fetch, now=checked, article_limit=200)
    health = [{
        "feed_id": row["feed_id"], "status": row["status"],
        "verified_links": row["verified_links"],
    } for row in inspected["sources"]]
    with tempfile.TemporaryDirectory(prefix="rasd-g40-unified-") as temp:
        selected = {}
        for raw in inspected["matched_public_articles"]:
            candidate = candidate_from_feed(raw, config, checked)
            if candidate is None:
                continue
            stamp = parsedate_to_datetime(candidate["published"]).astimezone(CAIRO)
            if stamp.date() != target_day or stamp > checked:
                continue
            row = {
                "id": candidate["id"], "headline": candidate["headline"],
                "publisher_excerpt": candidate.get("publisher_excerpt", ""),
                "source": candidate["source"], "url": candidate["url"],
                "published_at_cairo": stamp.strftime("%Y-%m-%d %H:%M %Z"),
                "published_display_cairo": cairo_display_time(stamp),
                "_sort": (stamp.date().isoformat(), "1", stamp.isoformat()),
                "_kind": "rss",
            }
            selected.setdefault(candidate["id"], row)
        result["rss_matched_on_day"] = len(selected)
        receipts = {}
        official_ok = False
        try:
            with official_driver_factory() as driver:
                links = driver.discover()
                corroboration = driver.discover()
                if (links != corroboration or len(links) != len(set(links))
                        or len(links) > 35 or not links):
                    raise ValueError("invalid_or_unstable_official_index")
                if any(canonical_official_article(url) != url for url in links):
                    raise ValueError("unapproved_official_article_link")
                result["official_index_urls"] = len(links)
                official_ok = True
                for link in links:
                    identifier = article_id(link)
                    destination = Path(temp) / (identifier + ".jpg")
                    outcome = driver.inspect(
                        link, keywords=config["keywords"],
                        target_day=target_day, image=destination)
                    status = outcome.get("status")
                    if status == "OUT_OF_WINDOW":
                        result["official_offday"] += 1
                        continue
                    if status == "EXCLUDED_NON_MATCHING_TERM":
                        continue
                    if status != "verified" or outcome.get("id") != identifier:
                        hold("official_article_unverifiable")
                        continue
                    digest = outcome.get("sha256")
                    if (not isinstance(digest, str) or len(digest) != 64
                            or not destination.is_file()):
                        hold("official_screenshot_missing")
                        continue
                    import hashlib
                    if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                        hold("official_screenshot_sha_mismatch")
                        continue
                    result["official_same_day"] += 1
                    if identifier in selected:
                        # Same canonical URL from two channels -> one article,
                        # but keep its original publisher provenance.
                        continue
                    selected[identifier] = {
                        "id": identifier, "headline": outcome["headline"],
                        "source": OFFICIAL_NAME, "url": link,
                        "publisher_excerpt": "",
                        "published_at_cairo": target_day.isoformat() + " (date only)",
                        "published_display_cairo": (
                            f"{target_day.isoformat()} — يوم النشر فقط؛ الساعة غير منشورة"),
                        "_sort": (target_day.isoformat(), "0", ""),
                        "_kind": "official",
                        "evidence_image_path": str(destination),
                    }
                    receipts[identifier] = {"id": identifier, "source": OFFICIAL_NAME,
                                             "status": "verified", "sha256": digest}
        except Exception:
            hold("official_index_unavailable")
        health.append({
            "feed_id": "mped-official",
            "status": "ok" if official_ok and not reasons else "failed",
            "verified_links": result["official_index_urls"],
        })
        rows = sorted(selected.values(), key=lambda x: x["_sort"], reverse=True)
        result["selected_unique_articles"] = len(rows)
        if len(rows) > MAX_ARTICLES:
            hold("above_15_article_production_cap_no_truncation")
        # Never silently suppress eligible report articles, including when a
        # source is down; output must be a HOLD rather than partial Word.
        if not any(x["status"] != "ok" for x in health) and not reasons:
            for row in rows:
                if row["_kind"] == "official":
                    continue
                dest = Path(temp) / (row["id"] + ".jpg")
                receipt = proof_capture(
                    row, config["feeds"], dest,
                    **({"capture": capture} if capture is not None else {}))
                if receipt["status"] != "verified":
                    hold("rss_original_page_screenshot_unverified")
                else:
                    row["evidence_image_path"] = str(dest)
                    receipts[row["id"]] = {**receipt, "id": row["id"],
                                           "source": row["source"]}
        result["source_health"] = health
        result["all_sources_healthy"] = all(x["status"] == "ok" for x in health)
        result["screenshots_verified"] = len(receipts)
        result["screenshots_missing"] = max(0, len(rows) - len(receipts))
        if not rows:
            hold("no_matching_articles_on_target_day")
        if not result["all_sources_healthy"]:
            hold("source_coverage_degraded")
        if len(receipts) != len(rows):
            hold("evidence_incomplete")
        if not reasons:
            for row in rows:
                row.pop("_sort")
                row.pop("_kind")
            start = datetime.combine(target_day, time.min, tzinfo=CAIRO)
            end = min(checked, start + timedelta(days=1))
            report = {
                "title": "رصد | تقرير وزارة التخطيط الموحد — نسخة اختبار موثقة",
                "display_window_start": cairo_display_time(start),
                "display_window_end": cairo_display_time(end),
                "coverage": "HEALTHY", "verified_links": (
                    inspected["public_verified_publisher_links"]
                    + result["official_index_urls"]),
                "articles": rows, "sources": [
                    {**s, "error_type": None} for s in health],
                "limitations": (
                    "هذا اختبار مصادر مصرية أصلية: حابي، المصري اليوم، والموقع "
                    "الرسمي لوزارة التخطيط. أخبار الوزارة الرسمية ذات تاريخ "
                    "يوم فقط دون ساعة مختلقة. قائمة الوزارة من أول صفحة "
                    "NewsList فقط؛ ليست أرشيفًا شاملًا. عناوين ناشرين مختلفين "
                    "قد تتناول نفس الحدث؛ العدد عدد روابط مستقلة وليس "
                    "عدد أحداث مستقلة. لا إرسال بريد ولا نشر عام."
                ),
            }
            receipt_list = [receipts[row["id"]] for row in rows]
            with tempfile.TemporaryDirectory(prefix="rasd-unified-docx-",
                                             dir=output_dir) as work:
                candidate = Path(work) / word_path.name
                render_docx(report, candidate)
                if (candidate.is_file() and candidate.stat().st_size > 3000
                        and word_images_match_capture_digests(
                            candidate, receipt_list)):
                    candidate.replace(word_path)
                    result.update(
                        status="READY_QA_ONLY", coverage="HEALTHY",
                        word_created=True, word_images_verified=True)
                else:
                    hold("word_article_image_binding_failed")
        result["failures"] = dict(sorted(reasons.items()))
        if result["status"] != "READY_QA_ONLY":
            word_path.unlink(missing_ok=True)
        result["word_is_ephemeral_no_public_artifact"] = True
        result["production_15_item_cap_intact"] = True
        return result


def main() -> None:
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--target-day", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = build_unified_word(
            Path("sources.json"), args.output_dir, target_day=args.target_day)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True), flush=True)
        if output["status"] != "READY_QA_ONLY":
            print("::warning::Unified Ministry Word HOLD; no final report", flush=True)
    except Exception:
        print("unified_ministry_report_failed_closed", flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
