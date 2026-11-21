"""First-party Al Mal shadow end-to-end Word: source HTML -> exact JPEG -> Word.

No production activation, SMTP, private ledger or artifact upload. Public
publisher pages and locally embedded original article screenshot only. A
failed screenshot blocks Word creation rather than substituting another image.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from unittest.mock import patch

from capture_public import APPROVED_PUBLISHERS
from cloud_proof_report import proof_capture, word_images_match_capture_digests
from daily_report import CAIRO, cairo_display_time, render_docx
from rasd_almal_original_html_research import research

HTML_SOURCE = {
    "id": "almal_html_shadow",
    "name": "Al Mal native publisher HTML",
    "allowed_article_hosts": ["almalnews.com", "www.almalnews.com"],
}


def build_shadow(now: datetime, *, discover=research,
                 capture=proof_capture, render=render_docx) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("almal_shadow_clock_timezone_required")
    checked = now.astimezone(timezone.utc)
    found = discover(now=checked)
    stories = found["stories"]
    if (not isinstance(stories, list) or len(stories) > 16 or
            len({x["id"] for x in stories}) != len(stories)):
        raise RuntimeError("almal_shadow_discovery_identity_hold")
    verified = []
    held = 0
    with tempfile.TemporaryDirectory(prefix="rasd-almal-shadow-") as temp:
        folder=Path(temp)
        # Allowlist addition remains strictly local to this no-send test.
        # Future production integration needs separate reviewed config.
        with patch.dict(APPROVED_PUBLISHERS, {
                "almalnews.com": frozenset(
                    {"almalnews.com", "www.almalnews.com"})}):
            for index, item in enumerate(stories):
                stamp = parsedate_to_datetime(item["published"])
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    raise RuntimeError("almal_shadow_original_date_hold")
                if not item["url"].startswith("https://almalnews.com/"):
                    raise RuntimeError("almal_shadow_original_url_hold")
                row={
                    "id":item["id"], "source":HTML_SOURCE["name"],
                    "headline":item["headline"], "url":item["url"],
                    "publisher_excerpt":item.get("publisher_excerpt", ""),
                    "published_at_cairo": stamp.astimezone(CAIRO).strftime(
                        "%Y-%m-%d %H:%M %Z"),
                    "published_display_cairo": cairo_display_time(stamp),
                }
                completed=checked.replace(minute=0,second=0,microsecond=0)
                row["hourly_publication_bucket"] = (
                    "within_previous_hour"
                    if completed - timedelta(hours=1) <= stamp.astimezone(timezone.utc) < completed
                    else "recovered_older")
                pic=folder / ("original-"+str(index)+".jpg")
                check=capture(row,[HTML_SOURCE],pic)
                if check.get("status")!="verified":
                    held+=1
                    continue
                verified.append(({**row,"evidence_image_path":str(pic)}, {
                    "status":"verified","sha256":check["sha256"]}))
        # Never misrepresent any skipped original as a genuine screenshot.
        result={
            "original_html_matches_72h":len(stories),
            "original_page_images_verified":len(verified),
            "original_page_images_held":held,
            "ministry_word_verified":False,
            "new_previous_complete_hour":sum(
                x[0]["hourly_publication_bucket"]=="within_previous_hour"
                for x in verified),
            "recovered_previous_hours":sum(
                x[0]["hourly_publication_bucket"]=="recovered_older"
                for x in verified),
            "production_activated":False,
            "smtp_sent":False, "private_ledger_modified":False,
        }
        if verified:
            report={
                "title":"رصد | اختبار مسار مصدر المال الساعي بدون إرسال",
                "ministry_media_grid":True,
                "report_period":"interval", "report_kind":"hourly",
                "coverage":"SOURCE_LIMITED",
                "hourly_in_period":result["new_previous_complete_hour"],
                "hourly_recovered":result["recovered_previous_hours"],
                "display_window_start":cairo_display_time(completed-timedelta(hours=1)),
                "display_window_end":cairo_display_time(completed),
                "sources":[{"feed_id":HTML_SOURCE["id"],"status":"ok",
                            "verified_links":len(stories)}],
                "verified_links":len(verified),
                "articles":[x[0] for x in verified],
                "limitations":"اختبار مصدر واحد فقط، دون نشر أو إرسال.",
            }
            word=folder / "RASD-AlMal-Shadow-Do-Not-Send.docx"
            render(report,word)
            if not word_images_match_capture_digests(
                    word, [x[1] for x in verified]):
                raise RuntimeError("almal_shadow_word_picture_digest_hold")
            result["ministry_word_verified"]=True
            result["ministry_word_bytes"]=word.stat().st_size
    return result


def main():
    outcome=build_shadow(datetime.now(timezone.utc))
    print("RASD_ALMAL_PIPELINE_ORIGINAL_HTML="+str(
        outcome["original_html_matches_72h"]))
    print("RASD_ALMAL_PIPELINE_ORIGINAL_PHOTOS="+str(
        outcome["original_page_images_verified"]))
    print("RASD_ALMAL_PIPELINE_PHOTO_HOLD="+str(
        outcome["original_page_images_held"]))
    print("RASD_ALMAL_PIPELINE_WORD_VERIFIED="+str(
        int(outcome["ministry_word_verified"])))
    print("RASD_ALMAL_PIPELINE_CURRENT_HOUR="+str(
        outcome["new_previous_complete_hour"]))
    print("RASD_ALMAL_PIPELINE_BACKLOG="+str(
        outcome["recovered_previous_hours"]))
    print("RASD_ALMAL_PIPELINE_NO_SEND_NO_ACTIVATION=1")


if __name__=="__main__":
    main()
