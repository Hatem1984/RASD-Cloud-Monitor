"""Run the ACTUAL scheduled hourly discovery and Word preparation, no send.

The owner-gated first-party HTML publisher is explicitly enabled only for
this isolated GitHub Actions job. It never touches production mail, private
ledger, mail recipients, or the daily report state. Uses genuine original
publisher screenshot + 14 native RSS source health.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cloud_proof_report import word_images_match_capture_digests
from daily_report import cairo_display_time
from scheduled_rasd import (
    discover_interval_news, prepare_source_limited_verified_word)
from rasd_original_html_source_gate import collection_origins


def main():
    if (os.environ.get("RASD_AUTOMATION_ENABLED")!="false"
            or os.environ.get("RASD_ALMAL_ORIGINAL_HTML_ENABLED")!="true"
            or os.environ.get("RASD_GMAIL_APP_PASSWORD")
            or os.environ.get("RASD_PRIVATE_LEDGER_TOKEN")):
        raise RuntimeError("html_integration_no_send_gate_invalid")
    config=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    if len(config["feeds"])!=14 or len(collection_origins(config))!=15:
        raise RuntimeError("html_staged_inventory_not_15_hold")
    clock=datetime.now(timezone.utc)
    hour_end=clock.replace(minute=0,second=0,microsecond=0)
    hour_start=hour_end-timedelta(hours=1)
    health=[]
    available=discover_interval_news(
        config,clock,source_records=health,allow_degraded=True,
        published_before=hour_end)
    native=[x for x in available
            if x["source"]=="Al Mal native publisher HTML"]
    print("RASD_HTML_15_ORIGINS_CHECKED="+str(len(health)))
    print("RASD_HTML_ALMAL_CANDIDATES_ORIGINAL="+str(len(native)))
    if not native:
        print("RASD_HTML_INTEGRATION_NO_OLD_ARTICLES=1")
        print("RASD_HTML_INTEGRATION_NO_SEND_NO_PRIVATE_LEDGER=1")
        return
    with tempfile.TemporaryDirectory(prefix="rasd-15-origins-no-send-") as temp:
        word,delivered,held,limited=prepare_source_limited_verified_word(
            native[:2], config, Path(temp),
            title="رصد | اختبار المصدر الأصلي ضمن التقرير الساعي",
            start=cairo_display_time(hour_start),
            end=cairo_display_time(hour_end),
            report_kind="hourly",source_records=health)
        from docx import Document
        doc=Document(word)
        if len(doc.inline_shapes)!=len(delivered):
            raise RuntimeError("html_integrated_word_missing_original_images")
        print("RASD_HTML_INTEGRATED_ORIGINAL_IMAGES="+str(len(delivered)))
        print("RASD_HTML_INTEGRATED_IMAGE_HOLD="+str(held))
        print("RASD_HTML_INTEGRATED_HEALTH_DEGRADED="+str(int(limited)))
        print("RASD_HTML_INTEGRATED_WORD_BYTES="+str(word.stat().st_size))
        print("RASD_HTML_INTEGRATED_WORD_VERIFIED=1")
    print("RASD_HTML_INTEGRATION_NO_SEND_NO_PRIVATE_LEDGER=1")


if __name__=="__main__":
    main()
