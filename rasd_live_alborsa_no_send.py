"""Real newsroom original-image DOCX QA for a reviewed native Alborsa feed.

No SMTP, no private state, no owner PC, no credentials. Only original-publisher
media that pass the same production URL/title/JPEG/DOCX digest checks.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from scheduled_rasd import discover_interval_news, prepare_source_limited_verified_word

def main():
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now = datetime.now(timezone.utc)
    health = []
    all_stories = discover_interval_news(
        config, now, allow_degraded=True, source_records=health)
    expected = [f["id"] for f in config["feeds"]]
    if [h["feed_id"] for h in health] != expected:
        raise RuntimeError("source_identity_changed")
    alborsa = [a for a in all_stories
               if a["source"] == "Alborsa native Egyptian Economy RSS"]
    if not alborsa:
        print("RASD_ALBORSA_LIVE=HOLD_NO_CURRENT_APPROVED_STORIES", flush=True)
        return
    dest = Path("rasd-live-qa")
    doc, proven, rejected, partial = prepare_source_limited_verified_word(
        alborsa[:3], config, dest, title="RASD — Alborsa publisher-original pilot (NO EMAIL)",
        start="2026-10-23T22:00:00+03:00",
        end=now.isoformat(), source_records=health)
    if not proven:
        raise RuntimeError("no_real_original_page_verified")
    print("RASD_ALBORSA_LIVE=VERIFIED_ORIGINAL_WORD"
          f" ARTICLES={len(proven)} JPEG_HELD={rejected}"
          f" SOURCE_LIMITED={partial} WORD_BYTES={doc.stat().st_size}"
          " EMAILS_SENT=0 PRIVATE_LEDGER_WRITES=0",
          flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RASD_ALBORSA_LIVE=HOLD_ORIGINAL_WORD_NOT_ACCEPTED"
              f" EXCEPTION={type(exc).__name__} EMAILS_SENT=0",
              flush=True)
        raise SystemExit(2) from None
