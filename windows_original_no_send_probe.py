"""Read-only GitHub-hosted Windows proof of genuine Hapi original-page JPEG/Word.

Zero secrets, mail, private ledger, uploads, source changes or browser bypass.
Only print allowlisted status and counts. Temporary JPEG/DOCX are discarded.
"""
from __future__ import annotations
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scheduled_rasd import discover_interval_news, prepare_word
from monitor import article_id

# Independently confirmed publisher-owned RSS URL from Oct22 acceptance.
# Historical experiment ONLY: never eligible for a new live scheduled email.
HISTORICAL_HAPI_URL = (
    "https://hapijournal.com/2026/10/22/"
    "%d9%88%d8%b2%d9%8a%d8%b1-%d8%a7%d9%84%d8%aa%d8%ae%d8%b7%d9%8a%d8%b7-"
    "%d9%86%d8%b3%d8%aa%d9%87%d8%af%d9%81-%d8%ae%d9%81%d8%b6-"
    "%d8%a7%d9%84%d8%af%d9%8a%d9%86-%d8%a7%d9%84%d8%ae%d8%a7%d8%b1%d8%ac%d9%8a/"
)


def main() -> None:
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now = datetime.now(timezone.utc)
    health = []
    stories = discover_interval_news(
        config, now, allow_degraded=True, source_records=health)
    candidates = [row for row in stories
                  if row["source"] == "Hapi native news RSS"
                  and row["url"].startswith("https://hapijournal.com/")]
    historical = not bool(candidates)
    current_matches = len(candidates)
    if historical:
        # Never misrepresent a 22 Oct historical headline as current news.
        candidates = [{
            "id": article_id(HISTORICAL_HAPI_URL),
            "source": "Hapi native news RSS",
            "headline": (
                "وزير التخطيط: نستهدف خفض الدين الخارجي تدريجيًا"
                " وتجاوز السداد حجم الاقتراض الجديد"
            ),
            "url": HISTORICAL_HAPI_URL,
            "publisher_excerpt": "",
            "published_at_cairo": "2026-10-22 19:52 EEST",
            "published_display_cairo": "22 أكتوبر 2026",
        }]
    source_health = {row["feed_id"]: row["status"] for row in health}
    with tempfile.TemporaryDirectory(prefix="rasd-win-original-") as temp:
        target = Path(temp)
        try:
            word, proof = prepare_word(
                candidates[:1], config, target,
                title="RASD Windows-origin real-page experimental proof ONLY",
                start=now.isoformat(), end=now.isoformat())
        except RuntimeError as exc:
            reason = str(exc)
            status = (
                "HOLD_ORIGINAL_PUBLISHER_CAPTURE"
                if reason == "publisher_screenshot_hold" else
                "HOLD_OTHER_INTEGRITY_FAILURE"
            )
            print(json.dumps({
                "mode": "windows_cloud_no_send",
                "status": status,
                "eligible": current_matches, "verified": 0,
                "sample": "historical_original" if historical else "live_rss",
                "source_health": source_health,
                "email_sent": False, "private_state_used": False,
            }), flush=True)
            if status == "HOLD_OTHER_INTEGRITY_FAILURE":
                raise SystemExit(2) from None
            return
        if (len(proof) != 1 or
                proof[0]["status"] != "verified" or
                not word.is_file() or word.stat().st_size < 3000):
            raise SystemExit("RASD_HOLD_PROOF_INTEGRITY")
        print(json.dumps({
            "mode": "windows_cloud_no_send",
            "status": "ONE_ORIGINAL_PUBLISHER_WORD_VERIFIED",
            "eligible": current_matches, "verified": 1,
            "sample": "historical_original" if historical else "live_rss",
            "source_health": source_health,
            "word_bytes": word.stat().st_size,
            "email_sent": False, "private_state_used": False,
        }), flush=True)


if __name__ == "__main__":
    main()
