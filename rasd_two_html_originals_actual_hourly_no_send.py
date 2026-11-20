"""Run 14 strict RSS + two gated original HTML publishers through ONE hourly Word.

Branch-only shadow proof. Explicit sender and private ledger are disabled.
Only Al Mal/Youm7 original-page news discovered from their own sites are
included in the temporary Word. Other verified RSS stories are intentionally
not claimed or sent in this no-send qualification.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path

from docx import Document

from daily_report import cairo_display_time
from rasd_original_html_source_gate import collection_origins
from scheduled_rasd import discover_interval_news,prepare_source_limited_verified_word

OPTIONAL={"Al Mal native publisher HTML","Youm7 first-party Ministry tag HTML"}


def main():
    if (os.environ.get("RASD_AUTOMATION_ENABLED")!="false"
            or os.environ.get("RASD_ALMAL_ORIGINAL_HTML_ENABLED")!="true"
            or os.environ.get("RASD_YOUM7_ORIGINAL_HTML_ENABLED")!="true"
            or os.environ.get("RASD_GMAIL_APP_PASSWORD")
            or os.environ.get("RASD_PRIVATE_LEDGER_TOKEN")):
        raise RuntimeError("sixteen_origin_no_send_guard_mismatch")
    config=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    if len(config["feeds"])!=14 or len(collection_origins(config))!=16:
        raise RuntimeError("sixteen_origin_list_mismatch")
    clock=datetime.now(timezone.utc)
    completed=clock.replace(minute=0,second=0,microsecond=0)
    health=[]
    collected=discover_interval_news(
        config,clock,allow_degraded=True,source_records=health,
        published_before=completed)
    specific=[x for x in collected if x["source"] in OPTIONAL]
    print("RASD_TWO_HTML_SOURCES_HEALTH_RECORDED="+str(
        sum(x["feed_id"] in ("almal_html","youm7_html") for x in health)))
    print("RASD_ALL_ORIGINS_HEALTH_RECORDED="+str(len(health)))
    print("RASD_TWO_HTML_ORIGINAL_DATED_CANDIDATES="+str(len(specific)))
    if not specific:
        print("RASD_TWO_HTML_NO_MATCHES_WINDOW_HOLD=1")
        print("RASD_TWO_HTML_NO_SEND=1")
        return
    with tempfile.TemporaryDirectory(prefix="rasd-sixteen-original-no-send-") as temp:
        word,delivered,held,degraded=prepare_source_limited_verified_word(
            specific[:8],config,Path(temp),
            title="رصد | اختبار دمج الموقعين في التقرير الساعي",
            start=cairo_display_time(completed-timedelta(hours=1)),
            end=cairo_display_time(completed),report_kind="hourly",
            source_records=health)
        if not word.is_file() or len(Document(word).inline_shapes)!=len(delivered):
            raise RuntimeError("sixteen_source_word_image_integrity_hold")
        print("RASD_TWO_HTML_ORIGINAL_PHOTO_VERIFIED="+str(len(delivered)))
        print("RASD_TWO_HTML_ORIGINAL_PHOTO_HELD="+str(held))
        print("RASD_TWO_HTML_HOURLY_FRESH="+str(sum(
            x.get("hourly_publication_bucket")=="within_previous_hour"
            for x in delivered)))
        print("RASD_TWO_HTML_RECOVERED_OLDER="+str(sum(
            x.get("hourly_publication_bucket")=="recovered_older"
            for x in delivered)))
        print("RASD_TWO_HTML_MINISTRY_WORD_VERIFIED=1")
    print("RASD_TWO_HTML_NO_SEND_NO_LEDGER_CHANGE=1")


if __name__=="__main__":
    main()
